import { FileText, Gavel, Image as ImageIcon, Video } from "lucide-react";
import { useTranslation } from "react-i18next";
import { documentKind } from "../lib/documentKind";

const ICONS = { video: Video, image: ImageIcon, notice: Gavel, document: FileText };

export default function DocumentKindIcon({ doc, size = 18 }) {
  const { t } = useTranslation("common");
  const kind = documentKind(doc);
  const Icon = ICONS[kind];
  const label = t(`documentKinds.${kind}`);
  return (
    <span className={`kind-icon kind-${kind}`} title={label} role="img" aria-label={label}>
      <Icon size={size} />
    </span>
  );
}
