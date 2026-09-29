import Avatar from "@atlaskit/avatar";
import Lozenge from "@atlaskit/lozenge";
import SectionMessage from "@atlaskit/section-message";
import Spinner from "@atlaskit/spinner";
import type { ReactNode } from "react";
import type { ChatResponse } from "../api/chat";
import SourceCitation from "./SourceCitation";

export type Message =
  | { id: string; role: "user"; text: string }
  | { id: string; role: "assistant"; response: ChatResponse }
  | { id: string; role: "error"; text: string };

type LozengeAppearance = "default" | "inprogress" | "moved" | "new" | "removed" | "success";

function statusFor(response: ChatResponse): { label: string; appearance: LozengeAppearance } {
  switch (response.classification) {
    case "ADVICE":
      return { label: "No investment advice", appearance: "moved" };
    case "UNSUPPORTED":
      return { label: "No predictions", appearance: "moved" };
    case "PII":
      return { label: "Personal data blocked", appearance: "removed" };
    default:
      return response.source ? { label: "Official source", appearance: "success" } : { label: "Not verified", appearance: "default" };
  }
}

function Entry({ author, avatar, status, children }: { author: string; avatar: ReactNode; status?: ReactNode; children: ReactNode }) {
  return (
    <li className="entry">
      {avatar}
      <div className="entry-body">
        <div className="entry-meta">
          <span className="entry-author">{author}</span>
          {status}
        </div>
        {children}
      </div>
    </li>
  );
}

const assistantAvatar = <Avatar appearance="square" size="medium" src="/favicon.svg" name="FAQ Assistant" />;
const userAvatar = <Avatar size="medium" name="You" />;

function SchemeNote({ response }: { response: ChatResponse }) {
  if (!response.scheme || response.classification !== "FACTUAL") return null;
  return (
    <p className="entry-note">
      Scheme: <strong>{response.scheme}</strong>
      {response.scheme_defaulted &&
        " — no scheme was named. Name a scheme or choose one in the Scheme field to ask about another."}
    </p>
  );
}

export function LoadingEntry() {
  return (
    <Entry author="FAQ Assistant" avatar={assistantAvatar}>
      <div className="loading-row" role="status">
        <Spinner size="small" label="Checking official sources" />
        Checking official sources...
      </div>
    </Entry>
  );
}

export default function ChatMessage({ message }: { message: Message }) {
  if (message.role === "user") {
    return (
      <Entry author="You" avatar={userAvatar}>
        <p className="entry-text">{message.text}</p>
      </Entry>
    );
  }
  if (message.role === "error") {
    return (
      <Entry author="FAQ Assistant" avatar={assistantAvatar}>
        <div className="entry-alert" role="alert">
          <SectionMessage appearance="error">
            <p>{message.text}</p>
          </SectionMessage>
        </div>
      </Entry>
    );
  }
  const { response } = message;
  const status = statusFor(response);
  return (
    <Entry author="FAQ Assistant" avatar={assistantAvatar} status={<Lozenge appearance={status.appearance}>{status.label}</Lozenge>}>
      <p className="entry-text">{response.answer}</p>
      <SchemeNote response={response} />
      {response.source && <SourceCitation source={response.source} />}
    </Entry>
  );
}
