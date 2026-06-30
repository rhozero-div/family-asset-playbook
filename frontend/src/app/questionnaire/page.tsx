import AppShell from "@/components/AppShell";
import QuestionnairePreview from "@/components/QuestionnairePreview";

export default function QuestionnairePage() {
  return (
    <AppShell eyebrow="Demo Route /questionnaire" title="Advisor Questionnaire Demo">
      <QuestionnairePreview />
    </AppShell>
  );
}
