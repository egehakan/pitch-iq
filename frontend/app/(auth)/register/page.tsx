"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { AuthBrand } from "@/components/auth/AuthShell";

export default function RegisterPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const res = await fetch("/api/session", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ action: "register", email, password, display_name: displayName }),
    });
    setLoading(false);
    if (res.ok) router.replace("/");
    else setError((await res.json().catch(() => ({}))).error ?? "Could not create the account.");
  };

  return (
    <div className="flex min-h-screen">
      <AuthBrand />
      <div className="flex w-full flex-col justify-center px-6 py-12 lg:w-1/2">
        <form onSubmit={submit} className="mx-auto w-full max-w-sm space-y-5">
          <div>
            <h1 className="font-display text-2xl font-bold tracking-tight text-text">Create your account</h1>
            <p className="mt-1 text-sm text-muted">Set your picks, then ask the companion anything.</p>
          </div>
          <Field label="Display name">
            <Input value={displayName} onChange={(e) => setDisplayName(e.target.value)} required autoFocus />
          </Field>
          <Field label="Email">
            <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </Field>
          <Field label="Password" hint="At least 6 characters." error={error ?? undefined}>
            <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} minLength={6} required />
          </Field>
          <Button type="submit" className="w-full" loading={loading}>
            Create account
          </Button>
          <p className="text-center text-sm text-muted">
            Already have an account?{" "}
            <Link href="/login" className="text-accent hover:underline">
              Sign in
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
