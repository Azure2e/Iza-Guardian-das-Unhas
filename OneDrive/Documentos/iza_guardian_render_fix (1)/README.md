# Iza Guardian das Unhas - App Django Completo

App mobile-first para salão de unhas "Iza Guardian das Unhas", com design inspirado na interface fornecida.

## Funcionalidades

- **Início**: Destaques e catálogo de modelos (mostra o nome do cliente logado)
- **Catálogo**: Lista completa de serviços/modelos de unhas
- **Agendamento**: Sistema completo de agendamento de horários
- **Favoritos**: Usuários podem favoritar modelos
- **Perfil completo**: Foto de perfil, nome, email e telefone (com edição)
- **Validação de email**: Formato + verificação de domínio real (MX records)
- **Painel Admin**: Django Admin completo para gerenciar serviços, categorias, agendamentos, favoritos e perfis

## Tecnologias

- Python + Django 5.x
- CSS customizado (tema rosa/mármore)
- JavaScript leve
- SQLite (fácil de rodar localmente)
- Imagens geradas para os modelos

## Como Rodar

1. **Instale as dependências** (em um terminal na pasta do projeto):

```bash
pip install -r requirements.txt
```

2. **Faça as migrações**:

```bash
python manage.py makemigrations
python manage.py migrate
```

3. **Crie um superusuário** (para acessar o admin):

```bash
python manage.py createsuperuser
```

4. **Carregue os dados de exemplo** (serviços com imagens):

```bash
python manage.py load_sample_data
```

5. **Rode o servidor**:

```bash
python manage.py runserver
```

6. **Acesse**:
   - App: http://127.0.0.1:8000/
   - Admin: http://127.0.0.1:8000/admin/

## Estrutura

- `catalog/` - Serviços, categorias e favoritos
- `appointments/` - Sistema de agendamentos
- `accounts/` - Autenticação
- `templates/` - Templates responsivos
- `static/` - CSS e JS
- `media/` - Imagens dos serviços (após carregar dados)

## Personalização

No Admin você pode:
- Adicionar/editar modelos de unhas
- Gerenciar agendamentos (confirmar, cancelar, etc.)
- Ver favoritos dos clientes

O design é totalmente responsivo e otimizado para mobile, seguindo o visual da interface original.

---

Criado para Iza Guardian das Unhas.
