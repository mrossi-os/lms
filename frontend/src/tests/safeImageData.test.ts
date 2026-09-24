import { describe, expect, it } from 'vitest'
import { safeImageData } from '@/oslms/utils/safeImageData'

describe('safeImageData', () => {
	it('keeps local raster, video and blob previews', () => {
		expect(safeImageData('data:image/png;base64,iVBORw0KGgo=')).toBe(
			'data:image/png;base64,iVBORw0KGgo='
		)
		expect(safeImageData('data:video/mp4;base64,AAAA')).toBe(
			'data:video/mp4;base64,AAAA'
		)
		expect(safeImageData('blob:http://site/1234')).toBe('blob:http://site/1234')
	})

	it('drops documents, scripts and empty values', () => {
		expect(safeImageData('data:image/svg+xml;base64,PHN2Zz4=')).toBeUndefined()
		expect(safeImageData('data:text/html;base64,PHNjcmlwdD4=')).toBeUndefined()
		expect(safeImageData('javascript:alert(1)')).toBeUndefined()
		expect(safeImageData(null)).toBeUndefined()
	})
})
