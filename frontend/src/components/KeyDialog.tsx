/** Access-key dialog: the write key (X-Access-Key) lives in localStorage, never in code. */
import { useEffect, useState } from "react";
import { KeyRound } from "lucide-react";
import { Button, Dialog, Field, Input } from "./ui/primitives";
import { accessKeyStore, attestorStore } from "@/lib/storage";

export function KeyDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [key, setKey] = useState("");
  const [who, setWho] = useState("");

  useEffect(() => {
    if (open) {
      setKey(accessKeyStore.get() ?? "");
      setWho(attestorStore.get());
    }
  }, [open]);

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Write access"
      footer={
        <>
          <Button
            variant="ghost"
            onClick={() => {
              accessKeyStore.set(null);
              setKey("");
              onClose();
            }}
          >
            Forget key
          </Button>
          <Button
            variant="primary"
            onClick={() => {
              accessKeyStore.set(key.trim() ? key.trim() : null);
              attestorStore.set(who.trim() || "person:anonymous");
              onClose();
            }}
          >
            Save
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <p className="text-xs text-muted">
          Reading TRACE is open to everyone. Appending or deciding claims needs the environment&apos;s access key, sent as the{" "}
          <code className="font-mono">X-Access-Key</code> header. It is stored in this browser only.
        </p>
        <Field label="Access key" hint="Ask the environment owner. The bundled mock accepts “demo-key”.">
          <Input value={key} onChange={(e) => setKey(e.target.value)} type="password" placeholder="X-Access-Key" />
        </Field>
        <Field label="Attested by" hint="Goes into every claim you append, e.g. person:j.berenguer or partner:demo-ngo.">
          <Input value={who} onChange={(e) => setWho(e.target.value)} placeholder="person:you" />
        </Field>
      </div>
    </Dialog>
  );
}

export function KeyButton({ onOpen }: { onOpen: () => void }) {
  const has = Boolean(accessKeyStore.get());
  return (
    <Button size="sm" variant="ghost" onClick={onOpen} title={has ? "Write key stored in this browser" : "No write key set — reading only"}>
      <KeyRound className={has ? "h-4 w-4 text-brand" : "h-4 w-4"} />
      <span className="hidden lg:inline">{has ? "key set" : "read-only"}</span>
    </Button>
  );
}
