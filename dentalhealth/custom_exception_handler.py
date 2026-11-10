from rest_framework.views import exception_handler
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken

def custom_exception_handler(exc, context):
    """Custom exception handler to format errors into an 'errors' array."""
    response = exception_handler(exc, context)

    if response is None:
        return response

    # Handle Simple JWT token errors
    if isinstance(exc, (TokenError, InvalidToken)):
        error_message = "The access token is invalid."
        if response.data.get('messages'):
            for message in response.data['messages']:
                if message.get('message') == "Token is expired":
                    error_message = "The access token has expired."
                    break
        response.data = {"errors": [error_message]}
        return response

    # Handle other exceptions (e.g., serializer errors)
    error_list = []
    if isinstance(response.data, dict):
        for field, messages in response.data.items():
            if field.lower() == 'non_field_errors':
                if isinstance(messages, list):
                    error_list.extend([str(msg) for msg in messages])
                else:
                    error_list.append(str(messages))
            elif field == 'detail' and not isinstance(messages, (list, dict)):
                # Handle non-field errors like AuthenticationFailed
                error_list.append(str(messages))
            else:
                if isinstance(messages, list):
                    for msg in messages:
                        if str(msg) == "This field is required.":
                            error_list.append(f"The {field} field is required.")
                        else:
                            error_list.append(f"{field.capitalize()}: {msg}")
                else:
                    if str(messages) == "This field is required.":
                        error_list.append(f"The {field} field is required.")
                    else:
                        error_list.append(f"{field.capitalize()}: {messages}")
    elif isinstance(response.data, list):
        error_list.extend([str(error) for error in response.data])
    else:
        error_list.append(str(response.data))

    response.data = {"errors": error_list}
    return response
