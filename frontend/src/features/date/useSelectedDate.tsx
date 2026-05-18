import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

interface SelectedDateContextValue {
  date: Date;
  setDate: (next: Date) => void;
}

const SelectedDateContext = createContext<SelectedDateContextValue | null>(null);

export function SelectedDateProvider({
  children,
  initialDate,
}: {
  children: ReactNode;
  initialDate?: Date;
}): JSX.Element {
  const [date, setDate] = useState<Date>(initialDate ?? new Date());
  const value = useMemo(() => ({ date, setDate }), [date]);
  return <SelectedDateContext.Provider value={value}>{children}</SelectedDateContext.Provider>;
}

export function useSelectedDate(): SelectedDateContextValue {
  const ctx = useContext(SelectedDateContext);
  if (!ctx) throw new Error("useSelectedDate must be used within SelectedDateProvider");
  return ctx;
}
