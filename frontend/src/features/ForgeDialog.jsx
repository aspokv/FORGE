import {useId} from "react";
import * as Dialog from "@radix-ui/react-dialog";
import {X} from "lucide-react";

export default function ForgeDialog({open, onOpenChange, title, description, children, busy=false, testId}) {
  const descriptionId=useId();
  return <Dialog.Root open={open} onOpenChange={value => { if (!busy) onOpenChange(value); }}>
    <Dialog.Portal>
      <Dialog.Overlay className="forge-dialog-overlay"/>
      <Dialog.Content className="forge-dialog" data-testid={testId} aria-describedby={description ? descriptionId : undefined}
        onEscapeKeyDown={event => { if (busy) event.preventDefault(); }}
        onPointerDownOutside={event => event.preventDefault()}>
        <div className="forge-dialog-heading"><Dialog.Title>{title}</Dialog.Title>
          <Dialog.Close className="forge-dialog-close" aria-label="Fechar" disabled={busy}><X size={20}/></Dialog.Close>
        </div>
        {description && <Dialog.Description id={descriptionId}>{description}</Dialog.Description>}
        {children}
      </Dialog.Content>
    </Dialog.Portal>
  </Dialog.Root>;
}
