(function () {
	if (typeof window === 'undefined') return

	const STORAGE_KEY = 'welcome_video_seen'
	const API_ENDPOINT =
		'/api/method/os_lms.os_lms.api.get_welcome_video_public_config'

	function isLoginPage() {
		return window.location.pathname.replace(/\/+$/, '') === '/login'
	}

	function hasSeenVideo() {
		try {
			return localStorage.getItem(STORAGE_KEY) === '1'
		} catch (e) {
			return false
		}
	}

	function markSeen() {
		try {
			localStorage.setItem(STORAGE_KEY, '1')
		} catch (e) {
			/* ignore */
		}
	}

	function buildModal(config) {
		const overlay = document.createElement('div')
		overlay.className = 'oslms-welcome-video-overlay'

		const card = document.createElement('div')
		card.className = 'oslms-welcome-video-card'

		const header = document.createElement('div')
		header.className = 'oslms-welcome-video-header'

		const title = document.createElement('h3')
		title.className = 'oslms-welcome-video-title'
		title.textContent = config.title || 'Benvenuto'

		const closeBtn = document.createElement('button')
		closeBtn.type = 'button'
		closeBtn.className = 'oslms-welcome-video-close'
		closeBtn.setAttribute('aria-label', 'Close')
		closeBtn.innerHTML = '&times;'

		header.appendChild(title)
		header.appendChild(closeBtn)

		const videoWrapper = document.createElement('div')
		videoWrapper.className = 'oslms-welcome-video-wrapper'

		const video = document.createElement('video')
		video.src = config.file_url
		video.controls = true
		video.autoplay = true
		video.className = 'oslms-welcome-video-player'

		videoWrapper.appendChild(video)

		const footer = document.createElement('div')
		footer.className = 'oslms-welcome-video-footer'

		const dismissBtn = document.createElement('button')
		dismissBtn.type = 'button'
		dismissBtn.className = 'btn btn-primary oslms-welcome-video-dismiss'
		dismissBtn.textContent = 'Chiudi'

		footer.appendChild(dismissBtn)

		card.appendChild(header)
		card.appendChild(videoWrapper)
		card.appendChild(footer)
		overlay.appendChild(card)

		function dismiss() {
			markSeen()
			try {
				video.pause()
			} catch (e) {
				/* ignore */
			}
			if (overlay.parentNode) {
				overlay.parentNode.removeChild(overlay)
			}
		}

		closeBtn.addEventListener('click', dismiss)
		dismissBtn.addEventListener('click', dismiss)
		video.addEventListener('ended', dismiss)

		return overlay
	}

	function showWelcomeVideo(config) {
		if (!config || !config.enabled || !config.file_url) return
		const modal = buildModal(config)
		document.body.appendChild(modal)
	}

	function init() {
		if (!isLoginPage()) return
		if (hasSeenVideo()) return

		fetch(API_ENDPOINT, { credentials: 'same-origin' })
			.then((res) => (res.ok ? res.json() : null))
			.then((payload) => {
				const config = payload && payload.message
				showWelcomeVideo(config)
			})
			.catch(() => {
				/* silent: login must keep working if the API fails */
			})
	}

	if (document.readyState === 'loading') {
		document.addEventListener('DOMContentLoaded', init)
	} else {
		init()
	}
})()
