from . import cart


class CartSecurityMiddleware:
    """Garante token de integridade do carrinho em toda requisição."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if hasattr(request, 'session'):
            cart.ensure_token(request.session)
        return self.get_response(request)
