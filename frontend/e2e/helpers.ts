import { expect, type Page } from '@playwright/test'

export const GOLDEN =
  'Main 6 saal se fabrication shop mein kaam karta hoon, CO2 aur argon dono welding karta hoon, plate aur pipe joint banata hoon, grinding karke finishing deta hoon'

export async function loginAs(page: Page, username: string) {
  await page.goto('/login')
  await page.getByTestId(`demo-${username}`).click()
  await page.getByTestId('login-submit').click()
  await expect(page).not.toHaveURL(/\/login/)
}
