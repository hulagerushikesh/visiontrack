import path from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"
export default defineConfig({plugins:[react(),tailwindcss()],publicDir:"assets",build:{outDir:"vercel_build/app",assetsDir:"static",emptyOutDir:true},resolve:{alias:{"@":path.resolve(__dirname,"./src")}}})
