import { createContext,useContext,useEffect,useMemo,useState } from 'react';
import { supabase } from '../lib/supabase';
import { getMyProfile,recordLoginEvent } from '../lib/api';

const AuthContext=createContext(null);

export function AuthProvider({children}){
  const[session,setSession]=useState(null);
  const[profile,setProfile]=useState(null);
  const[loading,setLoading]=useState(true);

  useEffect(()=>{
    let mounted=true;
    async function loadProfile(s){
      if(!s?.user){if(mounted)setProfile(null);return;}
      try{const data=await getMyProfile();if(mounted)setProfile(data);}catch(error){if(mounted){setProfile(null);console.error(error);}}
    }
    supabase.auth.getSession().then(async({data})=>{
      if(!mounted)return;
      setSession(data.session||null);
      await loadProfile(data.session);
      if(mounted)setLoading(false);
    });
    const{data:sub}=supabase.auth.onAuthStateChange((_event,s)=>{
      if(!mounted)return;
      setSession(s);
      queueMicrotask(async()=>{await loadProfile(s);if(mounted)setLoading(false);});
    });
    return()=>{mounted=false;sub.subscription.unsubscribe();};
  },[]);

  async function signIn(email,password){
    const{data,error}=await supabase.auth.signInWithPassword({email,password});
    if(error)throw error;
    await recordLoginEvent().catch(()=>{});
    return data;
  }
  async function signUp(email,password,username){
    const{data,error}=await supabase.auth.signUp({email,password,options:{data:{username}}});
    if(error)throw error;
    return data;
  }
  async function signOut(){await supabase.auth.signOut();setProfile(null);}
  async function refreshProfile(){if(!session?.user)return;setProfile(await getMyProfile());}

  const value=useMemo(()=>({session,user:session?.user||null,profile,loading,signIn,signUp,signOut,refreshProfile}),[session,profile,loading]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
export function useAuth(){const value=useContext(AuthContext);if(!value)throw new Error('useAuth must be used inside AuthProvider');return value;}
