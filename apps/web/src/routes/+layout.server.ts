import { env } from '$env/dynamic/private';

export const load = () => ({ simulation: env.OSCAR_APP_MODE === 'simulation' });
