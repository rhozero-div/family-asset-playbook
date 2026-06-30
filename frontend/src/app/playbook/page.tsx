import AppShell from "@/components/AppShell";
import PlaybookPreview from "@/components/PlaybookPreview";

export default function PlaybookPage() {
  return (
    <AppShell eyebrow="Demo Route /playbook" title="Client Playbook Demo">
      <PlaybookPreview />
    </AppShell>
  );
}
