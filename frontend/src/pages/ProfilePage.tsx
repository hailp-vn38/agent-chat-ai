import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useTranslation } from "react-i18next";
import { Loader2, Upload, AlertTriangle } from "lucide-react";
import { PageHead } from "@/components/PageHead";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  useUserProfile,
  useUpdateProfile,
  useChangePassword,
  useUploadAvatar,
  useDeleteAccount,
} from "@/queries";
import {
  updateProfileSchema,
  changePasswordSchema,
  type UpdateProfileFormData,
  type ChangePasswordFormData,
} from "@/lib/schemas/user-schemas";

// Common timezone options
const TIMEZONE_OPTIONS = [
  { value: "UTC", label: "UTC (Coordinated Universal Time)" },
  { value: "America/New_York", label: "America/New York (EST/EDT)" },
  { value: "America/Chicago", label: "America/Chicago (CST/CDT)" },
  { value: "America/Denver", label: "America/Denver (MST/MDT)" },
  { value: "America/Los_Angeles", label: "America/Los Angeles (PST/PDT)" },
  { value: "Europe/London", label: "Europe/London (GMT/BST)" },
  { value: "Europe/Paris", label: "Europe/Paris (CET/CEST)" },
  { value: "Europe/Berlin", label: "Europe/Berlin (CET/CEST)" },
  { value: "Asia/Tokyo", label: "Asia/Tokyo (JST)" },
  { value: "Asia/Shanghai", label: "Asia/Shanghai (CST)" },
  { value: "Asia/Hong_Kong", label: "Asia/Hong Kong (HKT)" },
  { value: "Asia/Singapore", label: "Asia/Singapore (SGT)" },
  { value: "Asia/Bangkok", label: "Asia/Bangkok (ICT)" },
  { value: "Asia/Ho_Chi_Minh", label: "Asia/Ho Chi Minh (ICT)" },
  { value: "Asia/Seoul", label: "Asia/Seoul (KST)" },
  { value: "Asia/Dubai", label: "Asia/Dubai (GST)" },
  { value: "Australia/Sydney", label: "Australia/Sydney (AEST/AEDT)" },
  { value: "Pacific/Auckland", label: "Pacific/Auckland (NZST/NZDT)" },
];

export const ProfilePage = () => {
  const { t } = useTranslation("profile");
  const { data: user, isLoading } = useUserProfile();
  const updateProfile = useUpdateProfile();
  const changePassword = useChangePassword();
  const uploadAvatar = useUploadAvatar();
  const deleteAccount = useDeleteAccount();

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [deleteConfirmText, setDeleteConfirmText] = useState("");

  // Profile form
  const profileForm = useForm<UpdateProfileFormData>({
    resolver: zodResolver(updateProfileSchema),
    defaultValues: {
      name: user?.name || "",
      timezone: user?.timezone || "UTC",
    },
    values: {
      name: user?.name || "",
      timezone: user?.timezone || "UTC",
    },
  });

  // Password form
  const passwordForm = useForm<ChangePasswordFormData>({
    resolver: zodResolver(changePasswordSchema),
    defaultValues: {
      current_password: "",
      new_password: "",
      confirm_password: "",
    },
  });

  const handleProfileSubmit = (data: UpdateProfileFormData) => {
    const updates: UpdateProfileFormData = {};
    if (data.name && data.name !== user?.name) updates.name = data.name;
    if (data.timezone && data.timezone !== user?.timezone)
      updates.timezone = data.timezone;

    if (Object.keys(updates).length > 0) {
      updateProfile.mutate(updates);
    }
  };

  const handlePasswordSubmit = (data: ChangePasswordFormData) => {
    changePassword.mutate({
      current_password: data.current_password,
      new_password: data.new_password,
    });
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file
    if (file.size > 5 * 1024 * 1024) {
      alert(t("max_file_size"));
      return;
    }

    if (
      !["image/jpeg", "image/jpg", "image/png", "image/webp"].includes(
        file.type
      )
    ) {
      alert(t("max_file_size"));
      return;
    }

    setSelectedFile(file);
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
  };

  const handleAvatarUpload = () => {
    if (selectedFile) {
      uploadAvatar.mutate(selectedFile, {
        onSuccess: () => {
          setSelectedFile(null);
          if (previewUrl) URL.revokeObjectURL(previewUrl);
          setPreviewUrl(null);
        },
      });
    }
  };

  const handleDeleteAccount = () => {
    if (deleteConfirmText === "DELETE") {
      deleteAccount.mutate();
    }
  };

  const getInitials = (name: string) => {
    return name
      .split(" ")
      .map((n) => n[0])
      .join("")
      .toUpperCase()
      .slice(0, 2);
  };

  if (isLoading) {
    return (
      <div className="container max-w-4xl mx-auto p-6 space-y-6">
        <div className="space-y-2">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-4 w-96" />
        </div>
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  if (!user) {
    return (
      <div className="container max-w-4xl mx-auto p-6">
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>{t("error")}</AlertTitle>
          <AlertDescription>{t("failed_to_load_profile")}</AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <>
      <PageHead
        title="profile:page.title"
        description="profile:page.description"
        translateTitle
        translateDescription
      />
      <div className="container max-w-4xl mx-auto p-6 space-y-6">
        <div>
          <h1 className="text-3xl font-bold">{t("profile_settings")}</h1>
          <p className="text-muted-foreground mt-2">
            {t("manage_account_settings")}
          </p>
        </div>

        <Tabs defaultValue="info" className="w-full">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="info">{t("profile_info")}</TabsTrigger>
            <TabsTrigger value="security">{t("security")}</TabsTrigger>
            <TabsTrigger value="danger">{t("danger_zone")}</TabsTrigger>
          </TabsList>

          {/* Profile Info Tab */}
          <TabsContent value="info" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>{t("profile_information")}</CardTitle>
                <CardDescription>{t("update_personal_info")}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Avatar Section */}
                <div className="flex items-center gap-6">
                  <Avatar className="h-24 w-24">
                    <AvatarImage
                      src={previewUrl || user.profile_image_base64 || undefined}
                      alt={user.name}
                    />
                    <AvatarFallback className="text-2xl">
                      {getInitials(user.name)}
                    </AvatarFallback>
                  </Avatar>
                  <div className="space-y-2">
                    <Input
                      id="avatar-upload"
                      type="file"
                      accept="image/jpeg,image/jpg,image/png,image/webp"
                      className="hidden"
                      onChange={handleFileSelect}
                    />
                    <label htmlFor="avatar-upload">
                      <Button type="button" variant="outline" asChild>
                        <span>{t("choose_image")}</span>
                      </Button>
                    </label>
                    {selectedFile && (
                      <Button
                        type="button"
                        onClick={handleAvatarUpload}
                        disabled={uploadAvatar.isPending}
                      >
                        {uploadAvatar.isPending ? (
                          <>
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            {t("uploading")}
                          </>
                        ) : (
                          <>
                            <Upload className="mr-2 h-4 w-4" />
                            {t("upload")}
                          </>
                        )}
                      </Button>
                    )}
                    <p className="text-sm text-muted-foreground">
                      {t("max_file_size")}
                    </p>
                  </div>
                </div>

                <Separator />

                {/* Profile Form */}
                <Form {...profileForm}>
                  <form
                    onSubmit={profileForm.handleSubmit(handleProfileSubmit)}
                    className="space-y-4"
                  >
                    <FormField
                      control={profileForm.control}
                      name="name"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>{t("name")}</FormLabel>
                          <FormControl>
                            <Input
                              placeholder={t("name_placeholder")}
                              {...field}
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <div>
                      <FormLabel>{t("email")}</FormLabel>
                      <Input
                        type="email"
                        value={user.email}
                        disabled
                        className="bg-muted"
                      />
                      <p className="text-sm text-muted-foreground mt-1">
                        {t("email_cannot_change")}
                      </p>
                    </div>

                    <FormField
                      control={profileForm.control}
                      name="timezone"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>{t("timezone")}</FormLabel>
                          <Select
                            onValueChange={field.onChange}
                            defaultValue={field.value}
                            value={field.value}
                          >
                            <FormControl>
                              <SelectTrigger>
                                <SelectValue
                                  placeholder={t("select_timezone")}
                                />
                              </SelectTrigger>
                            </FormControl>
                            <SelectContent>
                              {TIMEZONE_OPTIONS.map((tz) => (
                                <SelectItem key={tz.value} value={tz.value}>
                                  {tz.label}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                          <p className="text-sm text-muted-foreground">
                            {t("timezone_description")}
                          </p>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <Button
                      type="submit"
                      disabled={
                        updateProfile.isPending ||
                        !profileForm.formState.isDirty
                      }
                    >
                      {updateProfile.isPending ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          {t("saving")}
                        </>
                      ) : (
                        t("save_changes")
                      )}
                    </Button>
                  </form>
                </Form>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Security Tab */}
          <TabsContent value="security" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>{t("change_password")}</CardTitle>
                <CardDescription>
                  {t("change_password_description")}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Form {...passwordForm}>
                  <form
                    onSubmit={passwordForm.handleSubmit(handlePasswordSubmit)}
                    className="space-y-4"
                  >
                    <FormField
                      control={passwordForm.control}
                      name="current_password"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>{t("current_password")}</FormLabel>
                          <FormControl>
                            <Input type="password" {...field} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={passwordForm.control}
                      name="new_password"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>{t("new_password")}</FormLabel>
                          <FormControl>
                            <Input type="password" {...field} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={passwordForm.control}
                      name="confirm_password"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>{t("confirm_new_password")}</FormLabel>
                          <FormControl>
                            <Input type="password" {...field} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <Alert>
                      <AlertTriangle className="h-4 w-4" />
                      <AlertTitle>{t("password_warning")}</AlertTitle>
                      <AlertDescription>
                        {t("password_warning_description")}
                      </AlertDescription>
                    </Alert>

                    <Button type="submit" disabled={changePassword.isPending}>
                      {changePassword.isPending ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          {t("changing")}
                        </>
                      ) : (
                        t("change_password")
                      )}
                    </Button>
                  </form>
                </Form>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Danger Zone Tab */}
          <TabsContent value="danger" className="space-y-4">
            <Card className="border-destructive">
              <CardHeader>
                <CardTitle className="text-destructive">
                  {t("danger_zone_title")}
                </CardTitle>
                <CardDescription>
                  {t("danger_zone_description")}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <Alert variant="destructive">
                  <AlertTriangle className="h-4 w-4" />
                  <AlertTitle>{t("delete_account_warning")}</AlertTitle>
                  <AlertDescription>
                    {t("delete_account_warning_description")}
                  </AlertDescription>
                </Alert>

                <div className="space-y-2">
                  <p className="text-sm font-medium">
                    {t("what_happens_when_delete")}
                  </p>
                  <ul className="text-sm text-muted-foreground space-y-1 list-disc list-inside">
                    <li>{t("delete_account_point_1")}</li>
                    <li>{t("delete_account_point_2")}</li>
                    <li>{t("delete_account_point_3")}</li>
                    <li>{t("delete_account_point_4")}</li>
                  </ul>
                </div>

                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button variant="destructive" size="lg">
                      {t("delete_my_account")}
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>
                        {t("delete_account_confirm_title")}
                      </AlertDialogTitle>
                      <AlertDialogDescription className="space-y-4">
                        <p>{t("delete_account_confirm_description")}</p>
                        <div className="space-y-2">
                          <label className="text-sm font-medium text-foreground">
                            {t("type_delete_to_confirm")
                              .replace("<strong>", "")
                              .replace("</strong>", "")}
                          </label>
                          <Input
                            value={deleteConfirmText}
                            onChange={(e) =>
                              setDeleteConfirmText(e.target.value)
                            }
                            placeholder={t("delete_placeholder")}
                          />
                        </div>
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel
                        onClick={() => setDeleteConfirmText("")}
                      >
                        {t("common:cancel")}
                      </AlertDialogCancel>
                      <AlertDialogAction
                        onClick={handleDeleteAccount}
                        disabled={
                          deleteConfirmText !== "DELETE" ||
                          deleteAccount.isPending
                        }
                        className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                      >
                        {deleteAccount.isPending ? (
                          <>
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            {t("deleting")}
                          </>
                        ) : (
                          t("delete_my_account")
                        )}
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </>
  );
};

export default ProfilePage;
