import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAtom } from "jotai";
import {
  User,
  Settings,
  Globe,
  LogOut,
  ChevronDown,
  Check,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { useAuth } from "@/hooks";
import { languageAtom } from "@/store/language-atom";

interface UserDropdownMenuProps {
  className?: string;
}

export const UserDropdownMenu = ({ className }: UserDropdownMenuProps) => {
  const navigate = useNavigate();
  const { t, i18n } = useTranslation("navigation");
  const { user, logout } = useAuth();
  const [language, setLanguage] = useAtom(languageAtom);

  const changeLanguage = (lng: "en" | "vi") => {
    i18n.changeLanguage(lng);
    setLanguage(lng);
    localStorage.setItem("i18n", lng);
  };

  const getInitials = (name: string) => {
    return name
      .split(" ")
      .map((n) => n[0])
      .join("")
      .toUpperCase()
      .slice(0, 2);
  };

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  if (!user) return null;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className={`flex items-center gap-2 outline-none ${className}`}
      >
        <Avatar className="h-8 w-8">
          <AvatarImage
            src={user.profile_image_base64 || undefined}
            alt={user.name}
          />
          <AvatarFallback>{getInitials(user.name)}</AvatarFallback>
        </Avatar>
        <span className="text-sm font-medium hidden sm:inline">
          {user.name}
        </span>
        <ChevronDown className="h-4 w-4 text-muted-foreground" />
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuItem onClick={() => navigate("/profile")}>
          <User className="mr-2 h-4 w-4" />
          <span>{t("profile")}</span>
        </DropdownMenuItem>

        <DropdownMenuItem onClick={() => navigate("/settings")}>
          <Settings className="mr-2 h-4 w-4" />
          <span>{t("settings")}</span>
        </DropdownMenuItem>

        <DropdownMenuSeparator />

        <DropdownMenuSub>
          <DropdownMenuSubTrigger>
            <Globe className="mr-2 h-4 w-4" />
            <span>{t("language")}</span>
          </DropdownMenuSubTrigger>
          <DropdownMenuSubContent>
            <DropdownMenuItem onClick={() => changeLanguage("en")}>
              <span className="flex items-center justify-between w-full">
                English
                {language === "en" && <Check className="h-4 w-4 ml-2" />}
              </span>
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => changeLanguage("vi")}>
              <span className="flex items-center justify-between w-full">
                Tiếng Việt
                {language === "vi" && <Check className="h-4 w-4 ml-2" />}
              </span>
            </DropdownMenuItem>
          </DropdownMenuSubContent>
        </DropdownMenuSub>

        <DropdownMenuSeparator />

        <DropdownMenuItem onClick={handleLogout} className="text-destructive">
          <LogOut className="mr-2 h-4 w-4" />
          <span>{t("logout")}</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
};
