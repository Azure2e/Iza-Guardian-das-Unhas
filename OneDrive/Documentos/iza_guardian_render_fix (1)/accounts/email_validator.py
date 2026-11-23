import dns.resolver
from django.core.exceptions import ValidationError

def verify_email_domain(email):
    """
    Verifica se o domínio do email é real (possui registros MX válidos).
    """
    if not email or '@' not in email:
        raise ValidationError("Email inválido.")

    domain = email.split('@')[-1].strip().lower()

    try:
        # Verifica se existem registros MX
        answers = dns.resolver.resolve(domain, 'MX')
        if not answers:
            raise ValidationError(f"O domínio '{domain}' não possui servidor de email válido.")
        return True
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
        raise ValidationError(f"O domínio '{domain}' não existe ou não aceita emails.")
    except dns.resolver.NoNameservers:
        raise ValidationError(f"Não foi possível verificar o domínio '{domain}'.")
    except Exception:
        raise ValidationError(f"Erro ao verificar o domínio '{domain}'. Tente novamente.")
