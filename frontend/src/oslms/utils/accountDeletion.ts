import type { MobileRowGroup } from '@/components/Settings/mobileSettings'

// Self-service account deletion (ESG). The server decides who may delete
// (everyone but Administrator, see os_lms account_deletion.py); the SPA only
// hides the entry for the one account that would be refused anyway.
export const DELETE_ACCOUNT_ACTION = 'delete-account'

export const canDeleteOwnAccount = (user?: { name?: string } | null): boolean =>
	Boolean(user?.name) && user?.name !== 'Administrator'

// The phone "You" page lists the row right before "Log out", the other
// account-ending row. Tapping it opens DeleteAccountDialog.
export const withDeleteAccountRow = (
	groups: MobileRowGroup[],
	enabled: boolean,
): MobileRowGroup[] => {
	if (!enabled) return groups
	return groups.map((group) => {
		const at = group.rows.findIndex((row) => row.key === 'Log out')
		if (at < 0) return group
		const rows = [...group.rows]
		rows.splice(at, 0, {
			key: DELETE_ACCOUNT_ACTION,
			label: 'Delete account',
			icon: 'lucide-trash-2',
			action: DELETE_ACCOUNT_ACTION,
		})
		return { ...group, rows }
	})
}
