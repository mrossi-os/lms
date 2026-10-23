import { describe, expect, it } from 'vitest'
import {
	DELETE_ACCOUNT_ACTION,
	canDeleteOwnAccount,
	withDeleteAccountRow,
} from '../oslms/utils/accountDeletion'

const settings = () => [
	{
		key: 'Settings',
		rows: [
			{ key: 'colour-mode', label: 'Colour mode', action: 'colour-mode' },
			{ key: 'Log out', label: 'Log out', action: 'logout' },
		],
	},
]

describe('self-service account deletion entry', () => {
	it('puts its row right before Log out on the phone page', () => {
		const groups = withDeleteAccountRow(settings(), true)
		expect(groups[0].rows.map((row) => row.key)).toEqual([
			'colour-mode',
			DELETE_ACCOUNT_ACTION,
			'Log out',
		])
	})

	it('adds nothing for an account the server would refuse', () => {
		expect(withDeleteAccountRow(settings(), false)).toEqual(settings())
	})

	it('is offered to every signed-in user but Administrator', () => {
		expect(canDeleteOwnAccount({ name: 'student@example.com' })).toBe(true)
		expect(canDeleteOwnAccount({ name: 'Administrator' })).toBe(false)
		expect(canDeleteOwnAccount(null)).toBe(false)
	})
})
