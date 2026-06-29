import AppShell from "@/components/AppShell";
import QuestionnairePreview from "@/components/QuestionnairePreview";

export default function QuestionnairePage() {
  return (
    <AppShell eyebrow="Demo Route /questionnaire" title="顾问问卷页演示">
      <QuestionnairePreview />
    </AppShell>
  );
}
