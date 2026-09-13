import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"
const buttonVariants=cva("inline-flex items-center justify-center gap-2 rounded-full text-sm font-semibold transition-all outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:pointer-events-none disabled:opacity-50",{variants:{variant:{default:"bg-primary px-5 py-3 text-primary-foreground shadow-[0_0_35px_-10px_var(--primary)] hover:-translate-y-0.5 hover:bg-primary/90",outline:"border border-border bg-background/50 px-5 py-3 hover:border-primary/60 hover:bg-secondary",ghost:"px-3 py-2 text-muted-foreground hover:bg-secondary hover:text-foreground"},size:{default:"h-11",sm:"h-9",lg:"h-13 px-7 text-base",icon:"size-10 p-0"}},defaultVariants:{variant:"default",size:"default"}})
function Button({className,variant,size,asChild=false,...props}:React.ComponentProps<"button">&VariantProps<typeof buttonVariants>&{asChild?:boolean}){const Comp=asChild?Slot:"button";return <Comp className={cn(buttonVariants({variant,size,className}))}{...props}/>}
export {Button,buttonVariants}
