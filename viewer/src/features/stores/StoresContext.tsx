import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type Dispatch,
  type ReactNode,
  type SetStateAction,
} from "react";
import { fetchStoreLocations } from "@/shared/api/api";
import type { StoreLocation } from "@/shared/types/types";

interface StoresContextValue {
  storeLocations: StoreLocation[];
  storeLocationsLoading: boolean;
  showSettings: boolean;
  refreshStoreLocations: () => Promise<void>;
  setStoreLocations: Dispatch<SetStateAction<StoreLocation[]>>;
}

const StoresContext = createContext<StoresContextValue | null>(null);

export function useStores() {
  const value = useContext(StoresContext);
  if (!value) {
    throw new Error("useStores must be used within StoresProvider");
  }
  return value;
}

interface StoresProviderProps {
  user: object | null;
  children: ReactNode;
}

export function StoresProvider({ user, children }: StoresProviderProps) {
  const [storeLocations, setStoreLocations] = useState<StoreLocation[]>([]);
  const [storeLocationsLoading, setStoreLocationsLoading] = useState(false);

  const refreshStoreLocations = useCallback(() => {
    if (!user) return Promise.resolve();
    setStoreLocationsLoading(true);
    return fetchStoreLocations()
      .then(setStoreLocations)
      .catch(() => {})
      .finally(() => setStoreLocationsLoading(false));
  }, [user]);

  useEffect(() => {
    if (user) {
      void refreshStoreLocations();
    } else {
      setStoreLocations([]);
    }
  }, [user, refreshStoreLocations]);

  const showSettings = Boolean(user);

  const value = useMemo(
    (): StoresContextValue => ({
      storeLocations,
      storeLocationsLoading,
      showSettings,
      refreshStoreLocations,
      setStoreLocations,
    }),
    [storeLocations, storeLocationsLoading, showSettings, refreshStoreLocations],
  );

  return <StoresContext.Provider value={value}>{children}</StoresContext.Provider>;
}
