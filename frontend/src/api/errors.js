import axios from "axios";

/**
 * Every backend error (validation or AppError, see core/errors.py) comes
 * back as {"error": {"type", "message"}}. Components call this instead of
 * reading error.response.data by hand, so the envelope shape only lives in
 * one place on the frontend too.
 */
export function getErrorMessage(error) {
  if (axios.isAxiosError(error)) {
    const message = error.response?.data?.error?.message;
    if (typeof message === "string") {
      return message;
    }
    if (error.code === "ECONNABORTED") {
      return "The request timed out. Please try again.";
    }
    if (!error.response) {
      return "Could not reach the server. Please check your connection.";
    }
  }
  return "Something went wrong. Please try again.";
}
