import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react'
import { loadDashboardData } from './loadDashboardData'
import type { DashboardData } from './schema'

export type DashboardDataState =
  | { status: 'loading' }
  | { status: 'ready'; data: DashboardData }
  | { status: 'error'; error: Error; retry: () => void }

const DashboardDataContext = createContext<DashboardDataState | null>(null)

function asError(reason: unknown): Error {
  return reason instanceof Error ? reason : new Error('Dashboard data could not be loaded')
}

export function DashboardDataProvider({ children }: { children: ReactNode }) {
  const [attempt, setAttempt] = useState(0)
  const [state, setState] = useState<DashboardDataState>({ status: 'loading' })
  const retry = useCallback(() => {
    setState({ status: 'loading' })
    setAttempt((current) => current + 1)
  }, [])

  useEffect(() => {
    let active = true

    void loadDashboardData().then(
      (data) => {
        if (active) setState({ status: 'ready', data })
      },
      (reason: unknown) => {
        if (active) setState({ status: 'error', error: asError(reason), retry })
      },
    )

    return () => {
      active = false
    }
  }, [attempt, retry])

  return (
    <DashboardDataContext.Provider value={state}>
      {children}
    </DashboardDataContext.Provider>
  )
}

export function useDashboardData(): DashboardDataState {
  const state = useContext(DashboardDataContext)
  if (state === null) {
    throw new Error('useDashboardData must be used within DashboardDataProvider')
  }
  return state
}
