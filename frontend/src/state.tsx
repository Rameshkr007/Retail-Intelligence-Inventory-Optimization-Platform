import React, { createContext, useContext, useState } from "react";
import { getRole, getToken, setRole as saveRole, setToken as saveToken } from "./api";

interface AppState {
  isAuthed: boolean;
  role: string | null;
  login: (token: string, role: string) => void;
  logout: () => void;
  datasetId: number | null;
  setDatasetId: (id: number | null) => void;
  storeId: number;
  setStoreId: (id: number) => void;
  itemId: number;
  setItemId: (id: number) => void;
}

const Ctx = createContext<AppState | null>(null);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [role, setRoleState] = useState<string | null>(getRole());
  const [datasetId, setDatasetId] = useState<number | null>(null);
  const [storeId, setStoreId] = useState(1);
  const [itemId, setItemId] = useState(1);

  const login = (token: string, r: string) => {
    saveToken(token);
    saveRole(r);
    setRoleState(r);
  };
  const logout = () => {
    saveToken(null);
    saveRole(null);
    setRoleState(null);
  };

  return (
    <Ctx.Provider
      value={{
        isAuthed: !!getToken(),
        role,
        login,
        logout,
        datasetId,
        setDatasetId,
        storeId,
        setStoreId,
        itemId,
        setItemId,
      }}
    >
      {children}
    </Ctx.Provider>
  );
}

export function useApp() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
}
