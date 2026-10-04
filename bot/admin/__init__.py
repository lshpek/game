"""Telegram admin control centre.

The bot side of the internal control surface. Responsibilities are split on
purpose:

* :mod:`bot.admin.config`   - who is an admin, read from the same env the backend uses
* :mod:`bot.admin.client`   - the only place that talks to ``/api/admin/bot/*``
* :mod:`bot.admin.states`   - FSM states for short text input
* :mod:`bot.admin.ops`      - pending-operation registry behind the confirm buttons
* :mod:`bot.admin.formatters` - the Russian screen text
* :mod:`bot.admin.keyboards`  - inline keyboards and compact ``callback_data``
* :mod:`bot.admin.router`   - command, callback and text handlers

No business logic lives here: the bot renders screens, forwards intent and shows
results. Authorisation, validation, mutation and auditing all happen in the
backend, and every handler re-checks the admin id before acting.
"""

from admin.router import router

__all__ = ["router"]
