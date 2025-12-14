"use client";

import { useEffect, useState } from "react";
import { useAtom, useAtomValue } from "jotai";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Eye, EyeOff } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { useLogin } from "@/queries/auth-queries";
import { PageHead } from "@/components/PageHead";
import { authErrorAtom, isAuthenticatedAtom } from "@/store/auth-atom";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";

// Validation schema
const loginSchema = z.object({
  username: z.string().email("Invalid email format"),
  password: z.string().min(6, "Password must be at least 6 characters"),
});

type LoginFormValues = z.infer<typeof loginSchema>;

export const LoginPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation("auth");
  const { mutate: login, isPending } = useLogin();
  const [authError, setAuthError] = useAtom(authErrorAtom);
  const isAuthenticated = useAtomValue(isAuthenticatedAtom);
  const [showPassword, setShowPassword] = useState(false);

  const form = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      username: "",
      password: "",
    },
  });

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      // Clear auth error before redirecting
      setAuthError(null);
      navigate("/", { replace: true });
    }
  }, [isAuthenticated, navigate, setAuthError]);

  const onSubmit = (values: LoginFormValues) => {
    // Clear previous auth error
    setAuthError(null);

    // Submit login
    login(
      { username: values.username, password: values.password },
      {
        onSuccess: () => {
          // Clear form on successful login
          form.reset();
          // Redirect is handled by useEffect watching isAuthenticated
        },
        onError: (error: any) => {
          const message =
            error.response?.data?.message ||
            t("login.error_invalid_credentials");
          setAuthError(message);
        },
      }
    );
  };

  return (
    <>
      <PageHead
        title="auth:login.page_title"
        description="auth:login.page_description"
        translateTitle
        translateDescription
      />
      <div className="flex items-center justify-center min-h-screen bg-background px-4 relative">
        <div className="absolute top-4 right-4">
          <LanguageSwitcher />
        </div>
        <Card className="w-full max-w-md border-border/50 bg-card/50 backdrop-blur-sm">
          <CardHeader className="space-y-1 text-center">
            <CardTitle className="text-2xl font-bold">
              {t("login.welcome_back")}
            </CardTitle>
            <CardDescription>{t("login.subtitle")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 gap-2">
              <Button variant="outline" className="w-full" type="button">
                <svg
                  className="mr-2 h-4 w-4"
                  aria-hidden="true"
                  focusable="false"
                  data-prefix="fab"
                  data-icon="google"
                  role="img"
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 488 512"
                >
                  <path
                    fill="currentColor"
                    d="M488 261.8C488 403.3 391.1 504 248 504 110.8 504 0 393.2 0 256S110.8 8 248 8c66.8 0 123 24.5 166.3 64.9l-67.5 64.9C258.5 52.6 94.3 116.6 94.3 256c0 86.5 69.1 156.6 153.7 156.6 98.2 0 135-70.4 140.8-106.9H248v-85.3h236.1c2.3 12.7 3.9 24.9 3.9 41.4z"
                  ></path>
                </svg>
                {t("login.google_login")}
              </Button>
            </div>

            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <Separator className="w-full" />
              </div>
              <div className="relative flex justify-center text-xs uppercase">
                <span className="bg-background px-2 text-muted-foreground">
                  {t("login.or_continue")}
                </span>
              </div>
            </div>

            {authError && (
              <div className="bg-destructive/10 border border-destructive/50 rounded-md p-3">
                <p className="text-sm text-destructive">{authError}</p>
              </div>
            )}

            <Form {...form}>
              <form
                onSubmit={form.handleSubmit(onSubmit)}
                className="space-y-4"
              >
                <FormField
                  control={form.control}
                  name="username"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t("login.email_label")}</FormLabel>
                      <FormControl>
                        <Input
                          placeholder="m@example.com"
                          type="text"
                          disabled={isPending}
                          className="transition-all"
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="password"
                  render={({ field }) => (
                    <FormItem>
                      <div className="flex items-center justify-between">
                        <FormLabel>{t("login.password_label")}</FormLabel>
                        <button
                          type="button"
                          className="text-sm font-medium text-muted-foreground hover:text-primary hover:underline"
                          onClick={() => navigate("/forgot-password")}
                        >
                          {t("login.forgot_password_question")}
                        </button>
                      </div>
                      <FormControl>
                        <div className="relative">
                          <Input
                            placeholder={t("login.password_placeholder")}
                            type={showPassword ? "text" : "password"}
                            disabled={isPending}
                            className="transition-all pr-10"
                            {...field}
                          />
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            className="absolute right-0 top-0 h-full px-3 hover:bg-transparent"
                            onClick={() => setShowPassword(!showPassword)}
                            disabled={isPending}
                          >
                            {showPassword ? (
                              <EyeOff className="h-4 w-4 text-muted-foreground" />
                            ) : (
                              <Eye className="h-4 w-4 text-muted-foreground" />
                            )}
                            <span className="sr-only">
                              {showPassword ? "Hide password" : "Show password"}
                            </span>
                          </Button>
                        </div>
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <Button
                  type="submit"
                  disabled={isPending}
                  className="w-full transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isPending ? t("login.loading") : "Login"}
                </Button>
              </form>
            </Form>
          </CardContent>
          <CardFooter className="flex justify-center">
            <div className="text-sm text-muted-foreground">
              {t("login.no_account")}{" "}
              <button
                type="button"
                onClick={() => navigate("/register")}
                disabled={isPending}
                className="text-primary hover:underline disabled:opacity-50 disabled:cursor-not-allowed font-medium"
              >
                {t("login.register_link")}
              </button>
            </div>
          </CardFooter>
        </Card>
      </div>
    </>
  );
};

export default LoginPage;
