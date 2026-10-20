import { Terminal } from "lucide-react";
import { useTranslation } from "react-i18next";

import { MarkdownView } from "@/components/MarkdownView";
import { PageHeader } from "@/components/PageShell";
import cliEn from "../../../docs/cli.en.md?raw";
import cliZh from "../../../docs/cli.md?raw";

export function CliPage() {
  const { t, i18n } = useTranslation();
  const english = i18n.language.startsWith("en");
  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <PageHeader
        kind="guide"
        icon={Terminal}
        title={t("nav.cliDocs")}
        description={
          english
            ? "Command-line client for a running LiberAstra. Models stay on the services you connect."
            : "用命令行调用已经启动的 LiberAstra。模型仍在你接入的服务上运行。"
        }
      />
      <MarkdownView source={english ? cliEn : cliZh} />
    </div>
  );
}
