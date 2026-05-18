import { useSelectedDate } from "@/features/date/useSelectedDate";
import { SectionShell } from "@/shared/SectionShell";
import { AppointmentIcon } from "./icon";
import { AppointmentItem } from "./AppointmentItem";
import { EMPTY_APPOINTMENTS } from "./empty";
import { useAppointments } from "./useAppointments";

export function AppointmentsSection(): JSX.Element {
  const { date } = useSelectedDate();
  const q = useAppointments(date);
  const items = q.data?.items ?? [];
  return (
    <SectionShell
      title="Appointments"
      ariaLabel="Appointments"
      icon={<AppointmentIcon />}
      accentClass="border-appointment-50"
      isLoading={q.isLoading}
      isError={q.isError}
      count={items.length}
      emptyText={EMPTY_APPOINTMENTS}
      onRetry={() => q.refetch()}
    >
      {items.map((entry) => (
        <AppointmentItem key={entry.id} entry={entry} />
      ))}
    </SectionShell>
  );
}
