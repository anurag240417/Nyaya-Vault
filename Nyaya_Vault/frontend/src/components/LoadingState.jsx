import Lottie from 'lottie-react';
import loaderAnimation from '../assets/loader.json';

export default function LoadingState({fullPage=false,label='Loading…'}){
  return <div className={fullPage?'loading-state full-page':'loading-state'}>
    <Lottie animationData={loaderAnimation} loop autoplay style={{width:180,height:180}}/>
    <span>{label}</span>
  </div>
}
