import Button from "@atlaskit/button/new";
import SearchIcon from "@atlaskit/icon/core/search";

export const EXAMPLE_QUESTIONS = [
  "What is the expense ratio?",
  "What is the minimum SIP?",
  "How do I download my capital-gains statement?",
] as const;

interface Props {
  onSelect: (question: string) => void;
  disabled?: boolean;
}

export default function ExampleQuestions({ onSelect, disabled }: Props) {
  return (
    <div className="examples">
      {EXAMPLE_QUESTIONS.map((q) => (
        <Button key={q} iconBefore={SearchIcon} isDisabled={disabled} onClick={() => onSelect(q)}>
          {q}
        </Button>
      ))}
    </div>
  );
}
