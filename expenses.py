import os
import calendar
from datetime import date
from decimal import Decimal

from dateutil.parser import parse
from requests_oauthlib import OAuth2Session
from flask import Flask, request, redirect, session, url_for, render_template

app = Flask(__name__)

# This information is obtained upon registration of a new GitHub
client_id = os.environ.get('CLIENT_ID')
client_secret = os.environ.get('CLIENT_SECRET')
authorization_base_url = 'https://api.freeagent.com/v2/approve_app'
token_url = 'https://api.freeagent.com/v2/token_endpoint'

expenses_url='https://api.freeagent.com/v2/expenses?from_date={0}-{1}-{2}&to_date={3}-{4}-{5}'


@app.route("/")
def demo():
    """Step 1: User Authorization.

    Redirect the user/resource owner to the OAuth provider
    using an URL with a few key OAuth parameters.
    """
    freeagent = OAuth2Session(client_id)
    authorization_url, state = freeagent.authorization_url(authorization_base_url)

    # State is used to prevent CSRF, keep this for later.
    session['oauth_state'] = state
    return redirect(authorization_url)


# Step 2: User authorization, this happens on the provider.

@app.route("/callback", methods=["GET"])
def callback():
    """ Step 3: Retrieving an access token.

    The user has been redirected back from the provider to your registered
    callback URL. With this redirection comes an authorization code included
    in the redirect URL. We will use that to obtain an access token.
    """

    freeagent = OAuth2Session(client_id, state=session['oauth_state'])
    token = freeagent.fetch_token(token_url, client_secret=client_secret,
                               authorization_response=request.url)

    # At this point you can fetch protected resources but lets save
    # the token and show how this is done from a persisted token
    # in /profile.
    session['oauth_token'] = token

    return redirect(url_for('.expenses'))


@app.route("/expenses", methods=["GET"])
def expenses():
    """Fetching a protected resource using an OAuth 2 token.
    """
    today = date.today()
    first, last = calendar.monthrange(today.year, today.month)
    try:
        freeagent = OAuth2Session(client_id, token=session['oauth_token'])
    except KeyError:
        return redirect(url_for('.demo'))
    expenses = freeagent.get(expenses_url.format(today.year, today.month, first,
                                                 today.year, today.month, last)).json()

    # Strip out rebillable expenses and do some sorting of numbers.
    rebillable_expenses = [dict(description=v.get('description'),
                                amount=abs(Decimal(v.get('gross_value'))),
                                receipt_image=v.get('attachment').get('content_src_small'),
                                receipt=v.get('attachment').get('content_src'),
                                date=parse(v.get('dated_on')))
                                for v in expenses.get('expenses') if v.get('rebill_to_project')]

    # Sort them in date order.
    rebillable_expenses = sorted(rebillable_expenses, key=lambda k: k['date'])

    # Sum up the totals.
    total = sum([v.get('amount') for v in rebillable_expenses])

    return render_template('expenses.html', year=today.year,
                                            month=calendar.month_name[today.month],
                                            expenses=rebillable_expenses,
                                            total=total)

if __name__ == "__main__":
    # This allows us to use a plain HTTP callback
    os.environ['DEBUG'] = "1"
    app.secret_key = os.urandom(24)
    app.run(debug=True, port=5009)
