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
import { useRegister } from "@/queries/auth-queries";
import { PageHead } from "@/components/PageHead";
import { authErrorAtom, isAuthenticatedAtom } from "@/store/auth-atom";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";

/**
 * Registration form validation schema
 * Validates: name, email, password, confirmPassword
 */
const registerSchema = z
  .object({
    name: z.string().min(2, "Name must be at least 2 characters"),
    email: z.string().email("Invalid email format"),
    password: z.string().min(6, "Password must be at least 6 characters"),
    confirmPassword: z.string(),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "Passwords must match",
    path: ["confirmPassword"],
  });

type RegisterFormValues = z.infer<typeof registerSchema>;

export const RegisterPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation("auth");
  const { mutate: register, isPending } = useRegister();
  const [authError, setAuthError] = useAtom(authErrorAtom);
  const isAuthenticated = useAtomValue(isAuthenticatedAtom);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const form = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      name: "",
      email: "",
      password: "",
      confirmPassword: "",
    },
  });

  /**
   * Redirect to chat if already authenticated
   */
  useEffect(() => {
    if (isAuthenticated) {
      navigate("/chat", { replace: true });
    }
  }, [isAuthenticated, navigate]);

  /**
   * Form submission handler
   * Clears previous errors and submits registration
   */
  const onSubmit = (values: RegisterFormValues) => {
    // Prevent double submit when mutation is pending
    if (isPending) return;

    // Clear previous auth error
    setAuthError(null);

    // Submit registration (password field only - confirmPassword excluded)
    register(
      {
        name: values.name,
        email: values.email,
        password: values.password,
      },
      {
        onSuccess: () => {
          // Clear form on successful registration
          form.reset();
          // Clear auth error before redirecting
          setAuthError(null);
          // Redirect to login page
          navigate("/login", { replace: true });
        },
        onError: (error: any) => {
          const message =
            error.response?.data?.message || t("register.error_network");
          setAuthError(message);
        },
      }
    );
  };

  return (
    <>
      <PageHead
        title="auth:register.page_title"
        description="auth:register.page_description"
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
              {t("register.title")}
            </CardTitle>
            <CardDescription>{t("register.submit_button")}</CardDescription>
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
                Sign up with Google
              </Button>
            </div>

            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <Separator className="w-full" />
              </div>
              <div className="relative flex justify-center text-xs uppercase">
                <span className="bg-background px-2 text-muted-foreground">
                  Or continue with
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
                  name="name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t("register.name_label")}</FormLabel>
                      <FormControl>
                        <Input
                          placeholder={t("register.name_placeholder")}
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
                  name="email"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t("register.email_label")}</FormLabel>
                      <FormControl>
                        <Input
                          placeholder={t("register.email_placeholder")}
                          type="email"
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
                      <FormLabel>{t("register.password_label")}</FormLabel>
                      <FormControl>
                        <div className="relative">
                          <Input
                            placeholder={t("register.password_placeholder")}
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

                <FormField
                  control={form.control}
                  name="confirmPassword"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>
                        {t("register.confirm_password_label")}
                      </FormLabel>
                      <FormControl>
                        <div className="relative">
                          <Input
                            placeholder={t(
                              "register.confirm_password_placeholder"
                            )}
                            type={showConfirmPassword ? "text" : "password"}
                            disabled={isPending}
                            className="transition-all pr-10"
                            {...field}
                          />
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            className="absolute right-0 top-0 h-full px-3 hover:bg-transparent"
                            onClick={() =>
                              setShowConfirmPassword(!showConfirmPassword)
                            }
                            disabled={isPending}
                          >
                            {showConfirmPassword ? (
                              <EyeOff className="h-4 w-4 text-muted-foreground" />
                            ) : (
                              <Eye className="h-4 w-4 text-muted-foreground" />
                            )}
                            <span className="sr-only">
                              {showConfirmPassword
                                ? "Hide password"
                                : "Show password"}
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
                  {isPending
                    ? t("register.loading")
                    : t("register.submit_button")}
                </Button>
              </form>
            </Form>
          </CardContent>
          <CardFooter className="flex justify-center">
            <div className="text-sm text-muted-foreground">
              {t("register.already_account")}{" "}
              <button
                type="button"
                onClick={() => navigate("/login")}
                disabled={isPending}
                className="text-primary hover:underline disabled:opacity-50 disabled:cursor-not-allowed font-medium"
              >
                {t("register.login_link")}
              </button>
            </div>
          </CardFooter>
        </Card>
      </div>
    </>
  );
};

export default RegisterPage;
