export type PageAccess = 'challenge' | 'login_required' | 'restricted';

export function detectPageAccess(): PageAccess | undefined {
	const title = document.title.trim();
	const body = document.body?.innerText ?? '';
	if (/^(just a moment|attention required.*cloudflare|security verification)/i.test(title)
		|| (body.length < 4000 && /cloudflare/i.test(body)
			&& /performing security verification|verify you are human|checking your browser/i.test(body))) {
		return 'challenge';
	}
	if (/^access denied[.!]?$/i.test(title) && body.length < 4000) return 'restricted';

	const heading = document.querySelector('h1')?.textContent?.trim() ?? '';
	const loginPath = /\/(login|signin|sign-in|authwall|checkpoint)(\/|$)/i.test(location.pathname);
	const loginHeading = /^(sign in|log in|login|masuk)( to .*)?$/i.test(heading);
	if (loginPath || (loginHeading && document.querySelector('input[type="password"]'))) {
		return 'login_required';
	}
	return undefined;
}
