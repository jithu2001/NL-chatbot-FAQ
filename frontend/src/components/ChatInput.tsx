import Button from "@atlaskit/button/new";
import SendIcon from "@atlaskit/icon/core/send";
import Select from "@atlaskit/select";
import TextArea from "@atlaskit/textarea";
import { useState, type FormEvent, type KeyboardEvent } from "react";
import type { SchemeInfo } from "../api/chat";

const MAX_LENGTH = 500;

interface Option {
  label: string;
  value: string;
}

interface Props {
  onSubmit: (question: string) => void;
  disabled: boolean;
  schemes: SchemeInfo[];
  scheme: string;
  onSchemeChange: (scheme: string) => void;
}

const AUTO: Option = { label: "Auto (detect from question)", value: "" };

export default function ChatInput({ onSubmit, disabled, schemes, scheme, onSchemeChange }: Props) {
  const [value, setValue] = useState("");

  const options: Option[] = [AUTO, ...schemes.map((s) => ({ label: `${s.name} — ${s.category}`, value: s.name }))];
  const selected = options.find((o) => o.value === scheme) ?? AUTO;

  function submit(e?: FormEvent) {
    e?.preventDefault();
    const q = value.trim();
    if (!q || disabled) return;
    onSubmit(q);
    setValue("");
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  }

  return (
    <form onSubmit={submit}>
      {schemes.length > 0 && (
        <div className="composer-scheme">
          <label htmlFor="scheme-select" className="composer-field-label">
            Scheme
          </label>
          <div className="composer-scheme-select">
            <Select<Option>
            inputId="scheme-select"
            spacing="compact"
            menuPlacement="top"
            options={options}
            value={selected}
            onChange={(o) => onSchemeChange(o?.value ?? "")}
              isSearchable
            />
          </div>
        </div>
      )}
      <label htmlFor="question" className="visually-hidden">
        Question
      </label>
      <div className="composer-row">
        <TextArea
          id="question"
          value={value}
          maxLength={MAX_LENGTH}
          minimumRows={1}
          maxHeight="160px"
          resize="smart"
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Ask a factual question, e.g. What is the exit load of the liquid fund?"
          autoComplete="off"
        />
        <Button type="submit" appearance="primary" iconBefore={SendIcon} isDisabled={disabled || !value.trim()}>
          Ask
        </Button>
      </div>
      <p className="composer-help">
        Don't share PAN, Aadhaar, folio or account numbers, OTPs, phone numbers or email addresses.
        <span className="composer-keys"> Enter to ask · Shift + Enter for a new line.</span>
      </p>
    </form>
  );
}
