import type { NextAuthOptions } from "next-auth";
import GoogleProvider from "next-auth/providers/google";
import { authCallback } from "./api";

export const authOptions: NextAuthOptions = {
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID || "",
      clientSecret: process.env.GOOGLE_CLIENT_SECRET || "",
    }),
  ],
  session: {
    strategy: "jwt",
  },
  callbacks: {
    async signIn({ user, account }) {
      if (account?.provider === "google" && user.email) {
        try {
          const result = await authCallback({
            email: user.email,
            name: user.name || user.email,
            google_id: account.providerAccountId,
            avatar_url: user.image || undefined,
          });
          // Store the backend token on the user object for the jwt callback
          (user as any).backendToken = result.access_token;
          (user as any).backendRole = result.role;
          (user as any).backendUserId = result.user_id;
          return true;
        } catch (err) {
          console.error("Backend auth callback failed:", err);
          return false;
        }
      }
      return true;
    },
    async jwt({ token, user }) {
      if (user) {
        token.backendToken = (user as any).backendToken;
        token.role = (user as any).backendRole;
        token.backendUserId = (user as any).backendUserId;
      }
      return token;
    },
    async session({ session, token }) {
      (session as any).backendToken = token.backendToken;
      (session as any).role = token.role;
      (session as any).backendUserId = token.backendUserId;
      return session;
    },
  },
  pages: {
    signIn: "/",
  },
};
