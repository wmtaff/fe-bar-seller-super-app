import { createContext, useContext } from 'react';

export interface Me {
  email: string;
  persona_user_id: string;
  persona_name: string;
  role: string;
  persona_key: 'seller' | 'manager' | 'empty' | null;
  mapped: boolean;
  visible_owner_count: number;
}

export interface PersonaCtx {
  me: Me | null;
  /** Bumped after each persona switch so pages re-fetch. */
  version: number;
}

export const PersonaContext = createContext<PersonaCtx>({ me: null, version: 0 });
export const usePersona = () => useContext(PersonaContext);
