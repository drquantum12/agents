<!-- API documentation for vijayebhav backend-->


# Authentication and Authorization

/api/v1/auth/create-user
- POST: Create a new user in the system.
- Request Body:
    - userId (str): Unique identifier for the user.
    - name (str): Full name of the user.
    - email (str): Email address of the user.
    - photo_url (str): URL to the user's profile photo.
    - grade (str): Grade level of the user.
    - board (str): Educational board of the user.

- Response:
    - message (str): Confirmation message indicating successful user creation.
    - user (str): Unique identifier of the created user.