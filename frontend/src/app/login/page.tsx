"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { NexaraLogo } from "@/components/nexara-logo";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiClientError } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/auth-context";

const loginSchema = z.object({
  email: z.string().min(1, "Email is required").email("Enter a valid email address"),
  password: z.string().min(1, "Password is required"),
});

type LoginFormValues = z.infer<typeof loginSchema>;

export default function LoginPage() {
  const router = useRouter();
  const { login, isAuthenticated, isLoading } = useAuth();
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
  });

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      router.replace("/dashboard");
    }
  }, [isLoading, isAuthenticated, router]);

  async function onSubmit(values: LoginFormValues) {
    setSubmitError(null);
    setIsSubmitting(true);
    try {
      await login(values.email, values.password);
      router.replace("/dashboard");
    } catch (error) {
      // Same message for unknown e-mail and wrong password (the backend
      // answers 401 for both) so the form never reveals which e-mails exist.
      const status = error instanceof ApiClientError ? error.status : null;
      const message =
        status === 401
          ? "E-mail ou senha incorretos."
          : status === 429
            ? "Muitas tentativas de login. Aguarde alguns minutos e tente novamente."
            : "Não foi possível entrar agora. Tente novamente.";
      setSubmitError(message);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm space-y-8">
        <div className="flex flex-col items-center gap-2 text-center">
          <NexaraLogo className="scale-125" />
          <p className="text-sm text-muted-foreground">
            Todo dia sem o Nexara é receita que você não vê escapar.
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-base text-foreground">Sign in to your workspace</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  autoComplete="email"
                  placeholder="you@company.com"
                  aria-invalid={errors.email ? "true" : "false"}
                  {...register("email")}
                />
                {errors.email && <p className="text-sm text-destructive">{errors.email.message}</p>}
              </div>

              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  placeholder="••••••••"
                  aria-invalid={errors.password ? "true" : "false"}
                  {...register("password")}
                />
                {errors.password && (
                  <p className="text-sm text-destructive">{errors.password.message}</p>
                )}
              </div>

              {submitError && (
                <div
                  role="alert"
                  className="border-destructive/30 bg-destructive/10 rounded-md border px-3 py-2 text-sm text-destructive"
                >
                  {submitError}
                </div>
              )}

              <Button type="submit" className="w-full" disabled={isSubmitting}>
                {isSubmitting ? "Signing in…" : "Sign in"}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
