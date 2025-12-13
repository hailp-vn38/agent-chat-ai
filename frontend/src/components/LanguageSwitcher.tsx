import { useAtom } from "jotai";
import { useTranslation } from "react-i18next";
import { Globe } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { languageAtom } from "@/store/language-atom";

export const LanguageSwitcher = () => {
  const { i18n } = useTranslation();
  const [language, setLanguage] = useAtom(languageAtom);

  const changeLanguage = (lng: "en" | "vi") => {
    // Change i18next language first (will trigger event)
    i18n.changeLanguage(lng);
    // Explicitly sync to atom
    setLanguage(lng);
    // Ensure localStorage is updated
    localStorage.setItem("i18n", lng);
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon">
          <Globe className="h-5 w-5" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem
          onClick={() => changeLanguage("en")}
          className={language === "en" ? "bg-accent" : ""}
        >
          English
        </DropdownMenuItem>
        <DropdownMenuItem
          onClick={() => changeLanguage("vi")}
          className={language === "vi" ? "bg-accent" : ""}
        >
          Tiếng Việt
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

export default LanguageSwitcher;
