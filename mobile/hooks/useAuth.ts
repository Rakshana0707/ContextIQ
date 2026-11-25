/**
 * Authentication Hook for ContextIQ Mobile (Phase 5.6).
 */

import { useState, useEffect, useCallback } from 'react';
import { authService, AuthSession, MobileUser } from '../services/authService';
import { registerSessionExpiredHandler } from '../services/apiClient';

export function useAuth() {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Check existing stored session on mount
    authService
      .getCurrentSession()
      .then(sess => {
        setSession(sess);
        setIsLoading(false);
      })
      .catch(() => {
        setSession(null);
        setIsLoading(false);
      });

    // Register 401 session expiration handler
    registerSessionExpiredHandler(() => {
      setSession(null);
    });
  }, []);

  const login = useCallback(async (email: string, password?: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const sess = await authService.login(email, password);
      setSession(sess);
      return sess;
    } catch (err: any) {
      setError(err.message || 'Login failed');
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const register = useCallback(async (email: string, password: string, fullName: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const sess = await authService.register(email, password, fullName);
      setSession(sess);
      return sess;
    } catch (err: any) {
      setError(err.message || 'Registration failed');
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    setIsLoading(true);
    try {
      await authService.logout();
      setSession(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  return {
    isAuthenticated: !!session,
    user: session?.user || null,
    deviceId: session?.deviceId || null,
    isLoading,
    error,
    login,
    register,
    logout,
  };
}
