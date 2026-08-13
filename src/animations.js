/**
 * GSAP Animations — HH Goa 2026
 * On-load reveals
 */
import gsap from 'gsap';

export function initAnimations() {
  const tl = gsap.timeline({ delay: 0.2 });

  tl.to('.reveal-up', {
    opacity: 1,
    y: 0,
    duration: 0.8,
    stagger: 0.1,
    ease: 'power3.out',
  });

  tl.to('.reveal-left', {
    opacity: 1,
    x: 0,
    duration: 0.8,
    stagger: 0.1,
    ease: 'power3.out',
  }, '-=0.5');

  tl.to('.reveal-right', {
    opacity: 1,
    x: 0,
    duration: 0.8,
    stagger: 0.1,
    ease: 'power3.out',
  }, '-=0.8');
}
