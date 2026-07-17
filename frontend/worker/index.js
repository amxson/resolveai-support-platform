/** Keep the legacy Sites URL useful by forwarding it to the public Vercel app. */
export default {
  async fetch(request) {
    const sourceUrl = new URL(request.url)
    const destination = new URL(sourceUrl.pathname + sourceUrl.search, 'https://resolveai-support-platform.vercel.app')
    return Response.redirect(destination, 302)
  },
}

