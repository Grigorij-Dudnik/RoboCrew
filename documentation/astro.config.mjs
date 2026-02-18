// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

export default defineConfig({
  site: 'https://Grigorij-Dudnik.github.io/RoboCrew',
  base: 'RoboCrew',
  integrations: [
    starlight({
      title: 'RoboCrew',
      social: [
        { icon: 'github', label: 'GitHub', href: 'https://github.com/Grigorij-Dudnik/RoboCrew' }
      ],
      sidebar: [
        {
          label: 'Guides',
          items: [
            { 
              label: 'First Setup (Recommended if it\'s your first time)',
              items: [
                { label: 'Flashing Raspberry and plugin', slug: 'guides/setup/raspberry-and-plug' },
                { label: 'Installing RoboCrew', slug: 'guides/setup/installing-robocrew' },
                { label: 'Setting up udev rules', slug: 'guides/setup/udev-rules' },
              ],
            },
            { label: 'How to start (Short Guide)', slug: 'guides/start' },
            { 
              label: 'Examples',
              items: [
                { label: 'Movement', slug: 'guides/examples/movement' },
                { label: 'Audio and Voice', slug: 'guides/examples/audio' },
                { label: 'VLA as Tools', slug: 'guides/examples/vla-as-tools' },
              ],
            },
          ],
        },
        {
          label: 'Reference',
          autogenerate: { directory: 'reference' },
        },
      ],
    }),
  ],
});
