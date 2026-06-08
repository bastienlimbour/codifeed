import type {
  ErrorResponse,
  ValidationErrorDetail,
} from "@/types/generated/api.gen"

// Define possible API error response types
export type ApiErrorData = ErrorResponse | string | null

// Custom API Error class with proper typing
export class ApiError extends Error {
  public readonly response: Response
  public readonly data: ApiErrorData
  public readonly status: number
  public readonly url: string

  constructor(message: string, response: Response, data: ApiErrorData) {
    super(message)
    this.name = "ApiError"
    this.response = response
    this.data = data
    this.status = response.status
    this.url = response.url

    // Maintains proper stack trace for where our error was thrown (only available on V8)
    // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
    if (Error.captureStackTrace) {
      Error.captureStackTrace(this, ApiError)
    }
  }

  // Helper method to get a user-friendly error message
  getUserMessage(): string {
    const fallbackMessage =
      this.message.trim().length > 0
        ? this.message.trim()
        : this.getDefaultMessage()

    if (!this.data) {
      return fallbackMessage
    }

    if (typeof this.data === "string") {
      return this.data.trim().length > 0 ? this.data.trim() : fallbackMessage
    }

    if (
      this.data.details &&
      this.data.details.length > 0 &&
      this.data.message
    ) {
      const errors = this.formatValidationErrors(this.data.details)
      return `${this.data.message}\n${errors}`
    }

    if (this.data.message) {
      return this.data.message
    }

    return fallbackMessage
  }

  private formatValidationErrors(errors: ValidationErrorDetail[]): string {
    if (errors.length === 0) return ""

    return errors
      .map((error) => {
        const location = error.loc?.join("→") || "field"
        return `• ${location}: ${error.msg}`
      })
      .join("\n")
  }

  private getDefaultMessage(): string {
    switch (this.status) {
      case 400:
        return "Bad request"
      case 401:
        return "You are not authenticated"
      case 403:
        return "You don't have permission for this action"
      case 404:
        return "Resource not found"
      case 409:
        return "Resource already exists"
      case 422:
        return "Validation error"
      case 429:
        return "Too many requests. Please try again later"
      case 500:
        return "Internal server error. Please try again"
      case 502:
        return "Service temporarily unavailable"
      case 503:
        return "Service temporarily unavailable"
      default:
        return `Request failed with status ${this.status}`
    }
  }
}

// Helper function to extract meaningful error messages with type safety
export function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.getUserMessage()
  }
  if (isNetworkError(error)) {
    return "Network error. Please check your connection"
  }
  if (error instanceof Error) {
    return error.message
  }

  // Fallback for unknown error types
  return "An unexpected error occurred"
}

export function isNetworkError(error: unknown): boolean {
  return (
    error instanceof Error &&
    (error.message.includes("fetch") ||
      error.name === "NetworkError" ||
      !navigator.onLine)
  )
}

export class NotFoundPageError extends Error {
  constructor(message: string) {
    super(message)
    this.name = "NotFoundPageError"
  }
}
