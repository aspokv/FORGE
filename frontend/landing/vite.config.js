import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
export default defineConfig({base:'./',plugins:[react(),tailwindcss()],build:{target:'es2022',chunkSizeWarningLimit:1200},server:{allowedHosts:true}});
