import"./Bzak7iHL.js";import{p as Ge,g as Ye,f as Fe,b as m,d as n,j as d,c as t,r,t as h,a as Ke,i as fe,s as ze,e as x,k as B,u as g}from"./wmDFjFr_.js";import{s as u}from"./D4bZWLIo.js";import{d as Ve,b as pe,a as p,e as Je,f as v}from"./BKZDP7KO.js";import{i as Qe}from"./BS8SMZ8w.js";import{r as G,s as Y}from"./CHFC5TJK.js";import{b as F}from"./5M0apf-C.js";import{b as ve}from"./XmyshOgj.js";import{p as Xe}from"./Bfc47y5P.js";import{p as f}from"./Dy-S0HPn.js";import{r as _e}from"./BRxIPNE6.js";import{C as Ze}from"./5Ufi_5B0.js";import{g as et}from"./DVx7pC3Q.js";import{C as tt}from"./DtImEyrf.js";import{C as rt}from"./BxoBtc3e.js";import{T as P}from"./CnvijS-n.js";import{A as at,L as ot}from"./BGSmHUBu.js";import{u as st}from"./BLeFn5I5.js";var it=v('<button class="w-full text-left text-sm py-1.5 px-1 rounded-lg dark:text-gray-300 dark:hover:text-white hover:bg-black/5 dark:hover:bg-gray-850" type="button"><!></button>'),nt=v('<input class="w-full text-2xl font-medium bg-transparent outline-hidden font-primary" type="text" required=""/>'),lt=v('<div class="text-sm text-gray-500 shrink-0"> </div>'),dt=v('<input class="w-full text-sm disabled:text-gray-500 bg-transparent outline-hidden" type="text" required=""/>'),ut=v('<input class="w-full text-sm bg-transparent outline-hidden" type="text" required=""/>'),ct=v('<div class="text-sm text-gray-500"><div class=" bg-yellow-500/20 text-yellow-700 dark:text-yellow-200 rounded-lg px-4 py-3"><div> </div> <ul class=" mt-1 list-disc pl-4 text-xs"><li> </li> <li> </li></ul></div> <div class="my-3"> </div></div>'),mt=v('<!> <div class=" flex flex-col justify-between w-full overflow-y-auto h-full"><div class="mx-auto w-full md:px-0 h-full"><form class=" flex flex-col max-h-[100dvh] h-full"><div class="flex flex-col flex-1 overflow-auto h-0 rounded-lg"><div class="w-full mb-2 flex flex-col gap-0.5"><div class="flex w-full items-center"><div class=" shrink-0 mr-2"><!></div> <div class="flex-1"><!></div> <div class="self-center shrink-0"><button class="bg-gray-50 hover:bg-gray-100 text-black dark:bg-gray-850 dark:hover:bg-gray-800 dark:text-white transition px-2 py-1 rounded-full flex gap-1 items-center" type="button"><!> <div class="text-sm font-medium shrink-0"> </div></button></div></div> <div class=" flex gap-2 px-1 items-center"><!> <!></div></div> <div class="mb-2 flex-1 overflow-auto h-0 rounded-lg"><!></div> <div class="pb-3 flex justify-between"><div class="flex-1 pr-3"><div class="text-xs text-gray-500 line-clamp-2"><span class=" font-semibold dark:text-gray-200"> </span> <br/>— <span class=" font-medium dark:text-gray-400"> </span></div></div> <button class="px-3.5 py-1.5 text-sm font-medium bg-black hover:bg-gray-900 text-white dark:bg-white dark:text-black dark:hover:bg-gray-100 transition rounded-full" type="submit"> </button></div></div></form></div></div> <!>',1);function It(he,c){Ge(c,!0);const K=()=>fe(st,"$user",z),i=()=>fe(xe,"$i18n",z),[z,ge]=ze(),xe=Ye("i18n");let y=x(null),q=x(!1),$=x(!1),b=f(c,"edit",3,!1),ye=f(c,"clone",3,!1),be=f(c,"onSave",3,()=>{}),w=f(c,"id",7,""),k=f(c,"name",7,""),A=f(c,"meta",23,()=>({description:""})),_=f(c,"content",7,""),I=f(c,"accessControl",7,null),C=x("");const we=()=>{m(C,_(),!0)};let T=x(void 0),ke=`import os
import requests
from datetime import datetime


class Tools:
    def __init__(self):
        pass

    # Add your custom tools using pure Python code here, make sure to add type hints
    # Use Sphinx-style docstrings to document your tools, they will be used for generating tools specifications
    # Please refer to function_calling_filter_pipeline.py file from pipelines project for an example

    def get_user_name_and_email_and_id(self, __user__: dict = {}) -> str:
        """
        Get the user name, Email and ID from the user object.
        """

        # Do not include :param for __user__ in the docstring as it should not be shown in the tool's specification
        # The session user object will be passed as a parameter when the function is called

        print(__user__)
        result = ""

        if "name" in __user__:
            result += f"User: {__user__['name']}"
        if "id" in __user__:
            result += f" (ID: {__user__['id']})"
        if "email" in __user__:
            result += f" (Email: {__user__['email']})"

        if result == "":
            result = "User: Unknown"

        return result

    def get_current_time(self) -> str:
        """
        Get the current time in a more human-readable format.
        :return: The current time.
        """

        now = datetime.now()
        current_time = now.strftime("%I:%M:%S %p")  # Using 12-hour format with AM/PM
        current_date = now.strftime(
            "%A, %B %d, %Y"
        )  # Full weekday, month name, day, and year

        return f"Current Date and Time = {current_date}, {current_time}"

    def calculator(self, equation: str) -> str:
        """
        Calculate the result of a simple arithmetic equation.
        Only basic operators (+, -, *, /, **, %) and numbers are allowed.
        :param equation: The equation to calculate.
        """

        import ast
        import operator

        try:
            tree = ast.parse(equation, mode='eval')
            ops = {
                ast.Add: operator.add,
                ast.Sub: operator.sub,
                ast.Mult: operator.mul,
                ast.Div: operator.truediv,
                ast.Pow: operator.pow,
                ast.Mod: operator.mod,
                ast.USub: operator.neg,
                ast.UAdd: operator.pos,
            }
            def _eval(node):
                if isinstance(node, ast.Constant):
                    return node.value
                elif isinstance(node, ast.UnaryOp):
                    return ops[type(node.op)](_eval(node.operand))
                elif isinstance(node, ast.BinOp):
                    return ops[type(node.op)](_eval(node.left), _eval(node.right))
                else:
                    raise ValueError(f"Unsupported expression: {equation}")
            result = _eval(tree.body)
            return f"{equation} = {result}"
        except Exception as e:
            print(e)
            return "Invalid equation"

    def get_current_weather(self, city: str) -> str:
        """
        Get the current weather for a given city.
        :param city: The name of the city to get the weather for.
        :return: The current weather information or an error message.
        """
        api_key = os.getenv("OPENWEATHER_API_KEY")
        if not api_key:
            return (
                "API key is not set in the environment variable 'OPENWEATHER_API_KEY'."
            )

        base_url = "http://api.openweathermap.org/data/2.5/weather"
        params = {
            "q": city,
            "appid": api_key,
            "units": "metric",  # Optional: Use 'imperial' for Fahrenheit
        }

        try:
            response = requests.get(base_url, params=params)
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx and 5xx)
            data = response.json()

            if data.get("cod") != 200:
                return f"Error fetching weather data: {data.get('message')}"

            weather_description = data["weather"][0]["description"]
            temperature = data["main"]["temp"]
            humidity = data["main"]["humidity"]
            wind_speed = data["wind"]["speed"]

            return f"Weather in {city}: {temperature}°C"
        except requests.RequestException as e:
            return f"Error fetching weather data: {str(e)}"
`;const Ce=async()=>{be()({id:w(),name:k(),meta:A(),content:_(),access_control:I()})},V=async()=>{if(n(T)){_(n(C)),await B();const e=await n(T).formatPythonCodeHandler();await B(),_(n(C)),await B(),e&&(console.log("Code formatted successfully"),Ce())}};_e(()=>{_()&&we()}),_e(()=>{k()&&!b()&&!ye()&&w(k().replace(/\s+/g,"_").toLowerCase())});var J=mt(),Q=Fe(J);{let e=g(()=>{var a,l,o,s;return((o=(l=(a=K())==null?void 0:a.permissions)==null?void 0:l.sharing)==null?void 0:o.public_tools)||((s=K())==null?void 0:s.role)==="admin"});at(Q,{accessRoles:["read","write"],get allowPublic(){return n(e)},get show(){return n($)},set show(a){m($,a,!0)},get accessControl(){return I()},set accessControl(a){I(a)}})}var D=d(Q,2),X=t(D),E=t(X),Te=g(()=>Xe(()=>{b()?V():m(q,!0)})),Z=t(E),U=t(Z),S=t(U),M=t(S),Ee=t(M);{let e=g(()=>i().t("Back"));P(Ee,{get content(){return n(e)},children:(a,l)=>{var o=it(),s=t(o);rt(s,{strokeWidth:"2.5"}),r(o),pe("click",o,()=>{et("/workspace/tools")}),p(a,o)},$$slots:{default:!0}})}r(M);var j=d(M,2),Pe=t(j);{let e=g(()=>i().t("e.g. My Tools"));P(Pe,{get content(){return n(e)},placement:"top-start",children:(a,l)=>{var o=nt();G(o),h(s=>Y(o,"placeholder",s),[()=>i().t("Tool Name")]),F(o,k),p(a,o)},$$slots:{default:!0}})}r(j);var ee=d(j,2),H=t(ee),te=t(H);ot(te,{strokeWidth:"2.5",className:"size-3.5"});var re=d(te,2),qe=t(re,!0);r(re),r(H),r(ee),r(S);var ae=d(S,2),oe=t(ae);{var $e=e=>{var a=lt(),l=t(a,!0);r(a),h(()=>u(l,w())),p(e,a)},Ae=e=>{{let a=g(()=>i().t("e.g. my_tools"));P(e,{className:"w-full",get content(){return n(a)},placement:"top-start",children:(l,o)=>{var s=dt();G(s),h(R=>{Y(s,"placeholder",R),s.disabled=b()},[()=>i().t("Tool ID")]),F(s,w),p(l,s)},$$slots:{default:!0}})}};Qe(oe,e=>{b()?e($e):e(Ae,-1)})}var Ie=d(oe,2);{let e=g(()=>i().t("e.g. Tools for performing various operations"));P(Ie,{className:"w-full self-center items-center flex",get content(){return n(e)},placement:"top-start",children:(a,l)=>{var o=ut();G(o),h(s=>Y(o,"placeholder",s),[()=>i().t("Tool Description")]),F(o,()=>A().description,s=>A().description=s),p(a,o)},$$slots:{default:!0}})}r(ae),r(U);var N=d(U,2),De=t(N);ve(Ze(De,{get value(){return _()},lang:"python",boilerplate:ke,onChange:e=>{m(C,e,!0)},onSave:async()=>{n(y)&&n(y).requestSubmit()}}),e=>m(T,e,!0),()=>n(T)),r(N);var se=d(N,2),O=t(se),ie=t(O),W=t(ie),Ue=t(W,!0);r(W);var ne=d(W),le=d(ne,3),Se=t(le,!0);r(le),r(ie),r(O);var de=d(O,2),Me=t(de,!0);r(de),r(se),r(Z),r(E),ve(E,e=>m(y,e),()=>n(y)),r(X),r(D);var je=d(D,2);tt(je,{onconfirm:()=>{V()},get show(){return n(q)},set show(e){m(q,e,!0)},children:(e,a)=>{var l=ct(),o=t(l),s=t(o),R=t(s,!0);r(s);var ue=d(s,2),L=t(ue),He=t(L,!0);r(L);var ce=d(L,2),Ne=t(ce,!0);r(ce),r(ue),r(o);var me=d(o,2),Oe=t(me,!0);r(me),r(l),h((We,Re,Le,Be)=>{u(R,We),u(He,Re),u(Ne,Le),u(Oe,Be)},[()=>i().t("Please carefully review the following warnings:"),()=>i().t("Tools have a function calling system that allows arbitrary code execution."),()=>i().t("Do not install tools from sources you do not fully trust."),()=>i().t("I acknowledge that I have read and I understand the implications of my action. I am aware of the risks associated with executing arbitrary code and I have verified the trustworthiness of the source.")]),p(e,l)},$$slots:{default:!0}}),h((e,a,l,o,s)=>{u(qe,e),u(Ue,a),u(ne,` ${l??""} `),u(Se,o),u(Me,s)},[()=>i().t("Access"),()=>i().t("Warning:"),()=>i().t("Tools are a function calling system with arbitrary code execution"),()=>i().t("don't install random tools from sources you don't trust."),()=>i().t("Save")]),Je("submit",E,function(...e){var a;(a=n(Te))==null||a.apply(this,e)}),pe("click",H,()=>{m($,!0)}),p(he,J),Ke(),ge()}Ve(["click"]);export{It as T};
//# sourceMappingURL=DoVA1Pmj.js.map
