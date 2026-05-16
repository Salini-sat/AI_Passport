import { createContext, useContext, useState } from 'react'

const AppContext = createContext()

export function AppProvider({ children }) {
  const [passportData, setPassportData] = useState(null)
  const [storeUrl, setStoreUrl] = useState('')
  const [shopifyToken, setShopifyToken] = useState('')

  return (
    <AppContext.Provider value={{
      passportData, setPassportData,
      storeUrl, setStoreUrl,
      shopifyToken, setShopifyToken
    }}>
      {children}
    </AppContext.Provider>
  )
}

export const useApp = () => useContext(AppContext)
