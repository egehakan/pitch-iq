"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Button, buttonVariants } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { AuthBrand, GoogleMark } from "@/components/auth/AuthShell";
import { cn } from "@/lib/utils";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get("token");
    if (token) {
      fetch("/api/session", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ action: "token", token }),
      }).then(() => router.replace("/"));
    }
  }, [router]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const res = await fetch("/api/session", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ action: "login", email, password }),
    });
    setLoading(false);
    if (res.ok) router.replace("/");
    else setError((await res.json().catch(() => ({}))).error ?? "Email or password is wrong.");
  };

  return (
    <div className="flex min-h-screen">
      <AuthBrand />
      <div className="flex w-full flex-col justify-center px-6 py-12 lg:w-1/2">
        <form onSubmit={submit} className="mx-auto w-full max-w-sm space-y-5">
          <div>
            <h1 className="font-display text-2xl font-bold tracking-tight text-text">Welcome back</h1>
            <p className="mt-1 text-sm text-muted">Sign in to pick up where the match left off.</p>
          </div>
          <Field label="Email">
            <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus />
          </Field>
          <Field label="Password" error={error ?? undefined}>
            <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </Field>
          <Button type="submit" className="w-full" loading={loading}>
            Sign in
          </Button>
          <div className="flex items-center gap-3 text-[11px] text-faint">
            <span className="h-px flex-1 bg-line" />
            or
            <span className="h-px flex-1 bg-line" />
          </div>
          <a
            href={`${API_BASE}/api/auth/google/login`}
            className={cn(buttonVariants({ variant: "outline" }), "w-full")}
          >
            <GoogleMark />
            Continue with Google
          </a>
          <p className="text-center text-sm text-muted">
            New here?{" "}
            <Link href="/register" className="text-accent hover:underline">
              Create an account
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
