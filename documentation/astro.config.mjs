// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import { ion } from "starlight-ion-theme";


export default defineConfig({
  site: 'https://Grigorij-Dudnik.github.io/RoboCrew',
  base: 'RoboCrew',
  integrations: [
    starlight({
      title: 'RoboCrew',
      social: [
        { icon: 'github', label: 'GitHub', href: 'https://github.com/Grigorij-Dudnik/RoboCrew' },
				{ icon: 'discord', label: 'Discord', href: 'https://astro.build/chat' }

      ],
      sidebar: [
        {
          label: 'Guides',
          items: [
            { label: 'Quick Start Guide', link: 'guides/start' },
            { 
              label: 'First Setup (Recommended if it\'s your first time)',
              items: [
                { label: 'First time Setup', link: 'guides/setup/raspberry-and-plug' },
                { label: 'Installing RoboCrew', link: 'guides/setup/installing-robocrew' },
                { label: 'Setting up udev rules', link: 'guides/setup/udev-rules' },
              ],
            },
            { 
              label: 'Examples',
              items: [
                { label: 'Examples', link: 'guides/examples/movement' },
                { label: 'Audio and Voice', link: 'guides/examples/audio' },
                { label: 'Arm manipulation (VLA)', link: 'guides/examples/vla-as-tools' },
              ],
            },
          ],
        },
        {
          label: 'Reference',
          autogenerate: { directory: 'reference' },
        },
      ],
      plugins: [ion()],
    }),
  ],
});
