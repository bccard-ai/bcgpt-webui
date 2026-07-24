import"./Bzak7iHL.js";import{p as Nt,g as St,f as Vt,c as e,r,d as l,j as n,t as _,b as h,a as jt,i as Ht,s as Ot,e as I,k as O,u as g}from"./wmDFjFr_.js";import{s as u}from"./D4bZWLIo.js";import{d as Ut,b as Wt,a as f,e as zt,f as m}from"./BKZDP7KO.js";import{i as Lt}from"./BS8SMZ8w.js";import{r as U,s as W}from"./CHFC5TJK.js";import{b as z}from"./5M0apf-C.js";import{b as ot}from"./XmyshOgj.js";import{p as Gt}from"./Bfc47y5P.js";import{p as v}from"./Dy-S0HPn.js";import{r as lt}from"./BRxIPNE6.js";import{g as Jt}from"./DVx7pC3Q.js";import{C as Kt}from"./5Ufi_5B0.js";import{C as Qt}from"./DtImEyrf.js";import{B as Rt}from"./DIcOsvOY.js";import{T as C}from"./CnvijS-n.js";import{C as Xt}from"./BxoBtc3e.js";var Yt=m('<button class="w-full text-left text-sm py-1.5 px-1 rounded-lg dark:text-gray-300 dark:hover:text-white hover:bg-black/5 dark:hover:bg-gray-850" type="button"><!></button>'),Zt=m('<input class="w-full text-2xl font-medium bg-transparent outline-hidden font-primary" type="text" required=""/>'),te=m('<div class="text-sm text-gray-500 shrink-0"> </div>'),ee=m('<input class="w-full text-sm disabled:text-gray-500 bg-transparent outline-hidden" type="text" required=""/>'),re=m('<input class="w-full text-sm bg-transparent outline-hidden" type="text" required=""/>'),ae=m('<div class="text-sm text-gray-500"><div class=" bg-yellow-500/20 text-yellow-700 dark:text-yellow-200 rounded-lg px-4 py-3"><div> </div> <ul class=" mt-1 list-disc pl-4 text-xs"><li> </li> <li> </li></ul></div> <div class="my-3"> </div></div>'),ie=m('<div class=" flex flex-col justify-between w-full overflow-y-auto h-full"><div class="mx-auto w-full md:px-0 h-full"><form class=" flex flex-col max-h-[100dvh] h-full"><div class="flex flex-col flex-1 overflow-auto h-0 rounded-lg"><div class="w-full mb-2 flex flex-col gap-0.5"><div class="flex w-full items-center"><div class=" shrink-0 mr-2"><!></div> <div class="flex-1"><!></div> <div><!></div></div> <div class=" flex gap-2 px-1 items-center"><!> <!></div></div> <div class="mb-2 flex-1 overflow-auto h-0 rounded-lg"><!></div> <div class="pb-3 flex justify-between"><div class="flex-1 pr-3"><div class="text-xs text-gray-500 line-clamp-2"><span class=" font-semibold dark:text-gray-200"> </span> <br/>— <span class=" font-medium dark:text-gray-400"> </span></div></div> <button class="px-3.5 py-1.5 text-sm font-medium bg-black hover:bg-gray-900 text-white dark:bg-white dark:text-black dark:hover:bg-gray-100 transition rounded-full disabled:opacity-50 disabled:cursor-not-allowed" type="submit"> </button></div></div></form></div></div> <!>',1);function we(nt,c){Nt(c,!0);const o=()=>Ht(ct,"$i18n",dt),[dt,ut]=Ot(),ct=St("i18n");let x=I(null),L=!1,P=I(!1),ft=v(c,"onSave",3,()=>{}),b=v(c,"edit",3,!1),vt=v(c,"clone",3,!1),y=v(c,"id",7,""),w=v(c,"name",7,""),M=v(c,"meta",23,()=>({description:""})),p=v(c,"content",7,""),k=I("");const mt=()=>{h(k,p(),!0)};let $=I(void 0),pt=`"""
title: Example Filter
author: bcgpt
author_url: https://github.com/bccard-ai
funding_url: https://github.com/bccard-ai
version: 0.1
"""

from pydantic import BaseModel, Field
from typing import Optional


class Filter:
    class Valves(BaseModel):
        priority: int = Field(
            default=0, description="Priority level for the filter operations."
        )
        max_turns: int = Field(
            default=8, description="Maximum allowable conversation turns for a user."
        )
        pass

    class UserValves(BaseModel):
        max_turns: int = Field(
            default=4, description="Maximum allowable conversation turns for a user."
        )
        pass

    def __init__(self):
        # Indicates custom file handling logic. This flag helps disengage default routines in favor of custom
        # implementations, informing the WebUI to defer file-related operations to designated methods within this class.
        # Alternatively, you can remove the files directly from the body in from the inlet hook
        # self.file_handler = True

        # Initialize 'valves' with specific configurations. Using 'Valves' instance helps encapsulate settings,
        # which ensures settings are managed cohesively and not confused with operational flags like 'file_handler'.
        self.valves = self.Valves()
        pass

    def inlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        # Modify the request body or validate it before processing by the chat completion API.
        # This function is the pre-processor for the API where various checks on the input can be performed.
        # It can also modify the request before sending it to the API.
        print(f"inlet:{__name__}")
        print(f"inlet:body:{body}")
        print(f"inlet:user:{__user__}")

        if __user__.get("role", "admin") in ["user", "admin"]:
            messages = body.get("messages", [])

            max_turns = min(__user__["valves"].max_turns, self.valves.max_turns)
            if len(messages) > max_turns:
                raise Exception(
                    f"Conversation turn limit exceeded. Max turns: {max_turns}"
                )

        return body

    def outlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        # Modify or analyze the response body after processing by the API.
        # This function is the post-processor for the API, which can be used to modify the response
        # or perform additional checks and analytics.
        print(f"outlet:{__name__}")
        print(f"outlet:body:{body}")
        print(f"outlet:user:{__user__}")

        return body
`;const _t=async()=>{L=!0,ft()({id:y(),name:w(),meta:M(),content:p()})},G=async()=>{if(l($)){p(l(k)),await O();const t=await l($).formatPythonCodeHandler();await O(),p(l(k)),await O(),t&&(console.log("Code formatted successfully"),_t())}};lt(()=>{p()&&mt()}),lt(()=>{w()&&!b()&&!vt()&&y(w().replace(/\s+/g,"_").toLowerCase())});var J=ie(),A=Vt(J),K=e(A),F=e(K),ht=g(()=>Gt(()=>{b()?G():h(P,!0)})),Q=e(F),q=e(Q),B=e(q),E=e(B),gt=e(E);{let t=g(()=>o().t("Back"));C(gt,{get content(){return l(t)},children:(i,d)=>{var a=Yt(),s=e(a);Xt(s,{strokeWidth:"2.5"}),r(a),Wt("click",a,()=>{Jt("/admin/functions")}),f(i,a)},$$slots:{default:!0}})}r(E);var T=n(E,2),xt=e(T);{let t=g(()=>o().t("e.g. My Filter"));C(xt,{get content(){return l(t)},placement:"top-start",children:(i,d)=>{var a=Zt();U(a),_(s=>W(a,"placeholder",s),[()=>o().t("Function Name")]),z(a,w),f(i,a)},$$slots:{default:!0}})}r(T);var R=n(T,2),bt=e(R);{let t=g(()=>o().t("Function"));Rt(bt,{type:"muted",get content(){return l(t)}})}r(R),r(B);var X=n(B,2),Y=e(X);{var yt=t=>{var i=te(),d=e(i,!0);r(i),_(()=>u(d,y())),f(t,i)},wt=t=>{{let i=g(()=>o().t("e.g. my_filter"));C(t,{className:"w-full",get content(){return l(i)},placement:"top-start",children:(d,a)=>{var s=ee();U(s),_(j=>{W(s,"placeholder",j),s.disabled=b()},[()=>o().t("Function ID")]),z(s,y),f(d,s)},$$slots:{default:!0}})}};Lt(Y,t=>{b()?t(yt):t(wt,-1)})}var kt=n(Y,2);{let t=g(()=>o().t("e.g. A filter to remove profanity from text"));C(kt,{className:"w-full self-center items-center flex",get content(){return l(t)},placement:"top-start",children:(i,d)=>{var a=re();U(a),_(s=>W(a,"placeholder",s),[()=>o().t("Function Description")]),z(a,()=>M().description,s=>M().description=s),f(i,a)},$$slots:{default:!0}})}r(X),r(q);var D=n(q,2),$t=e(D);ot(Kt($t,{get value(){return p()},lang:"python",boilerplate:pt,onchange:t=>{h(k,t,!0)},onSave:async()=>{l(x)&&l(x).requestSubmit()}}),t=>h($,t,!0),()=>l($)),r(D);var Z=n(D,2),N=e(Z),tt=e(N),S=e(tt),Ft=e(S,!0);r(S);var et=n(S),rt=n(et,3),It=e(rt,!0);r(rt),r(tt),r(N);var V=n(N,2),Ct=e(V,!0);r(V),r(Z),r(Q),r(F),ot(F,t=>h(x,t),()=>l(x)),r(K),r(A);var Pt=n(A,2);Qt(Pt,{onconfirm:()=>{G()},get show(){return l(P)},set show(t){h(P,t,!0)},children:(t,i)=>{var d=ae(),a=e(d),s=e(a),j=e(s,!0);r(s);var at=n(s,2),H=e(at),Mt=e(H,!0);r(H);var it=n(H,2),At=e(it,!0);r(it),r(at),r(a);var st=n(a,2),qt=e(st,!0);r(st),r(d),_((Bt,Et,Tt,Dt)=>{u(j,Bt),u(Mt,Et),u(At,Tt),u(qt,Dt)},[()=>o().t("Please carefully review the following warnings:"),()=>o().t("Functions allow arbitrary code execution."),()=>o().t("Do not install functions from sources you do not fully trust."),()=>o().t("I acknowledge that I have read and I understand the implications of my action. I am aware of the risks associated with executing arbitrary code and I have verified the trustworthiness of the source.")]),f(t,d)},$$slots:{default:!0}}),_((t,i,d,a)=>{u(Ft,t),u(et,` ${i??""} `),u(It,d),V.disabled=L,u(Ct,a)},[()=>o().t("Warning:"),()=>o().t("Functions allow arbitrary code execution"),()=>o().t("don't install random functions from sources you don't trust."),()=>o().t("Save")]),zt("submit",F,function(...t){var i;(i=l(ht))==null||i.apply(this,t)}),f(nt,J),jt(),ut()}Ut(["click"]);export{we as F};
//# sourceMappingURL=DBhVqIvz.js.map
