import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"
const buttonVariants=cva("inline-flex items-center justify-center gap-2 rounded-xl text-sm font-semibold transition-all outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",{variants:{variant:{default:"bg-primary px-5 py-3 text-primary-foreground shadow-[0_10px_30px_-12px_var(--primary)] hover:-translate-y-0.5 hover:bg-primary/90 hover:shadow-[0_14px_34px_-12px_var(--primary)]",outline:"border border-border bg-white/75 px-5 py-3 shadow-sm hover:-translate-y-0.5 hover:border-primary/35 hover:bg-white",secondary:"bg-secondary px-5 py-3 text-foreground hover:bg-secondary/75",ghost:"px-3 py-2 text-muted-foreground hover:bg-secondary hover:text-foreground"},size:{default:"h-11",sm:"h-9",lg:"h-13 px-7 text-base",icon:"size-10 p-0"}},defaultVariants:{variant:"default",size:"default"}})
function Button({className,variant,size,asChild=false,...props}:React.ComponentProps<"button">&VariantProps<typeof buttonVariants>&{asChild?:boolean}){const Comp=asChild?Slot:"button";return <Comp className={cn(buttonVariants({variant,size,className}))}{...props}/>}
export {Button,buttonVariants}
