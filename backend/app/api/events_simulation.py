from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.forecast_inventory import _dataset_schema, _get_features, _sanitize
from app.core.auth import get_current_user
from app.core.database import get_db
from app.inventory.optimization import InventoryPolicy, compute_inventory
from app.models.orm import AuditLog, BusinessEvent, SimulatedInventoryState, User

router = APIRouter(prefix="/api", tags=["events_simulation"])


class EventCreate(BaseModel):
    name: str
    start_date: str
    end_date: str
    expected_demand_impact_pct: float  # e.g. 40 for Diwali +40% expected uplift — a business input, not fitted data


@router.post("/events")
async def create_event(dataset_id: int, event: EventCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Create a custom festival/promotion event. This is explicitly an
    OPTIONAL BUSINESS INPUT (spec §26) — it does not claim the dataset
    contains historical event data unless it actually does."""
    be = BusinessEvent(
        dataset_version_id=dataset_id, name=event.name, start_date=event.start_date,
        end_date=event.end_date, expected_demand_impact_pct=event.expected_demand_impact_pct,
        created_by=user.email,
    )
    db.add(be)
    db.add(AuditLog(user_email=user.email, action="create_business_event", entity=f"event:{event.name}"))
    db.commit()
    db.refresh(be)
    return {"event_id": be.id, "name": be.name, "expected_demand_impact_pct": be.expected_demand_impact_pct,
            "note": "This is a user-declared business assumption, not derived from historical data."}


@router.get("/events")
async def list_events(dataset_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    events = db.query(BusinessEvent).filter(BusinessEvent.dataset_version_id == dataset_id).all()
    return [{"event_id": e.id, "name": e.name, "start_date": e.start_date, "end_date": e.end_date,
             "expected_demand_impact_pct": e.expected_demand_impact_pct} for e in events]


@router.post("/events/{event_id}/apply")
async def apply_event_to_inventory(
    event_id: int, dataset_id: int, store_id: int, item_id: int,
    lead_time_days: int = 7, service_level: float = 0.95, ordering_cost: float = 50.0,
    holding_cost_per_unit_per_year: float = 5.0, current_stock: float = 100.0,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    """Applies a declared event's demand-impact assumption to the real
    inventory formula for one SKU — same computation path as
    /api/inventory/optimize, just with the event's growth assumption
    layered on."""
    event = db.query(BusinessEvent).filter(BusinessEvent.id == event_id, BusinessEvent.dataset_version_id == dataset_id).first()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found for this dataset.")

    schema = _dataset_schema(db, dataset_id)
    store_col, item_col, sales_col = schema["store_col"], schema["item_col"], schema["sales_col"]
    features = _get_features(db, dataset_id, schema)
    history = features[(features[store_col] == store_id) & (features[item_col] == item_id)]
    if history.empty:
        raise HTTPException(status_code=404, detail="No history found for this store/item combination.")

    base_avg = float(history[sales_col].tail(90).mean())
    base_std = float(history[sales_col].tail(90).std())
    base_annual = float(history[sales_col].tail(365).sum()) if len(history) >= 30 else base_avg * 365
    growth_factor = 1 + event.expected_demand_impact_pct / 100.0

    policy = InventoryPolicy(lead_time_days=lead_time_days, service_level=service_level, ordering_cost=ordering_cost,
                              holding_cost_per_unit_per_year=holding_cost_per_unit_per_year, current_stock=current_stock)
    result = compute_inventory(base_avg * growth_factor, base_std * growth_factor, base_annual * growth_factor, policy)

    return _sanitize({
        "event": event.name, "expected_demand_impact_pct": event.expected_demand_impact_pct,
        "store_id": store_id, "item_id": item_id,
        "forecast_demand_with_event": round(base_avg * growth_factor, 2),
        **result.__dict__,
    })


# ---- Real-Time Inventory Simulation (explicitly SIMULATED) ------------------

@router.post("/simulation/sale")
async def simulate_sale(
    dataset_id: int, store_id: int, item_id: int, quantity: float = 1.0,
    lead_time_days: int = 7, service_level: float = 0.95, ordering_cost: float = 50.0,
    holding_cost_per_unit_per_year: float = 5.0,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    """SIMULATED sale: decrements a mutable simulated stock value and
    recomputes risk/recommendation. This is a simulation for demo purposes,
    not a live POS feed — the response is explicitly labeled as such."""
    schema = _dataset_schema(db, dataset_id)
    store_col, item_col, sales_col = schema["store_col"], schema["item_col"], schema["sales_col"]
    features = _get_features(db, dataset_id, schema)
    history = features[(features[store_col] == store_id) & (features[item_col] == item_id)]
    if history.empty:
        raise HTTPException(status_code=404, detail="No history found for this store/item combination.")

    state = db.query(SimulatedInventoryState).filter(
        SimulatedInventoryState.dataset_version_id == dataset_id,
        SimulatedInventoryState.store_id == store_id,
        SimulatedInventoryState.item_id == item_id,
    ).first()
    if state is None:
        # Initialize simulated stock at ~15 days of average demand — a
        # documented starting assumption, since no real stock feed exists.
        avg0 = float(history[sales_col].tail(90).mean())
        state = SimulatedInventoryState(dataset_version_id=dataset_id, store_id=store_id, item_id=item_id,
                                         current_stock=avg0 * 15)
        db.add(state)
        db.commit()
        db.refresh(state)

    state.current_stock = max(0.0, state.current_stock - quantity)
    state.updated_at = datetime.now(timezone.utc)
    db.commit()

    avg = float(history[sales_col].tail(90).mean())
    std = float(history[sales_col].tail(90).std())
    annual = float(history[sales_col].tail(365).sum()) if len(history) >= 30 else avg * 365
    policy = InventoryPolicy(lead_time_days=lead_time_days, service_level=service_level, ordering_cost=ordering_cost,
                              holding_cost_per_unit_per_year=holding_cost_per_unit_per_year, current_stock=state.current_stock)
    result = compute_inventory(avg, std, annual, policy)

    return _sanitize({
        "status": "SIMULATED",
        "dataset_id": dataset_id, "store_id": store_id, "item_id": item_id,
        "quantity_sold": quantity, "current_stock_after_sale": round(state.current_stock, 2),
        **result.__dict__,
    })


@router.get("/simulation/state")
async def get_simulation_state(dataset_id: int, store_id: int, item_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    state = db.query(SimulatedInventoryState).filter(
        SimulatedInventoryState.dataset_version_id == dataset_id,
        SimulatedInventoryState.store_id == store_id,
        SimulatedInventoryState.item_id == item_id,
    ).first()
    if state is None:
        return {"status": "SIMULATED", "initialized": False, "current_stock": None}
    return {"status": "SIMULATED", "initialized": True, "current_stock": round(state.current_stock, 2),
            "updated_at": state.updated_at.isoformat()}
