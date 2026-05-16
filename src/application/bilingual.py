"""Bilingual (EN/FR) helper for backend error messages and labels."""


TRANSLATIONS = {
    # Generic errors
    'resource_not_found': {'en': 'Resource not found', 'fr': 'Ressource non trouvée'},
    'internal_error': {'en': 'Internal server error', 'fr': 'Erreur interne du serveur'},
    'access_forbidden': {'en': 'Access forbidden', 'fr': 'Accès interdit'},
    'auth_required': {'en': 'Authentication required', 'fr': 'Authentification requise'},
    'invalid_token': {'en': 'Invalid or expired token', 'fr': 'Jeton invalide ou expiré'},
    'missing_field': {'en': 'Missing required field: {field}', 'fr': 'Champ requis manquant : {field}'},
    'no_data': {'en': 'No data provided', 'fr': 'Aucune donnée fournie'},
    'operation_failed': {'en': 'Operation failed', 'fr': 'Opération échouée'},
    'success': {'en': 'Success', 'fr': 'Succès'},
    'created': {'en': 'Created successfully', 'fr': 'Créé avec succès'},
    'updated': {'en': 'Updated successfully', 'fr': 'Mis à jour avec succès'},
    'deleted': {'en': 'Deleted successfully', 'fr': 'Supprimé avec succès'},

    # Auth errors
    'invalid_credentials': {'en': 'Invalid email or password', 'fr': 'Email ou mot de passe invalide'},
    'account_disabled': {'en': 'Account is disabled. Contact your administrator.', 'fr': 'Compte désactivé. Contactez votre administrateur.'},
    'email_required': {'en': 'Please enter a valid email address', 'fr': 'Veuillez entrer une adresse email valide'},
    'password_required': {'en': 'Please enter your password', 'fr': 'Veuillez entrer votre mot de passe'},
    'too_many_attempts': {'en': 'Too many attempts. Try again in 5 minutes.', 'fr': 'Trop de tentatives. Réessayez dans 5 minutes.'},
    'passwords_mismatch': {'en': 'Passwords do not match', 'fr': 'Les mots de passe ne correspondent pas'},
    'voucher_invalid': {'en': 'Invalid voucher format', 'fr': 'Format de code invalide'},
    'voucher_not_found': {'en': 'Voucher code not found', 'fr': 'Code de voucher non trouvé'},
    'voucher_used': {'en': 'Voucher has already been used', 'fr': 'Ce voucher a déjà été utilisé'},
    'voucher_expired': {'en': 'Voucher has expired', 'fr': 'Ce voucher a expiré'},
    'fill_required': {'en': 'Please fill all required fields', 'fr': 'Veuillez remplir tous les champs obligatoires'},

    # SMS
    'sms_sent': {'en': 'SMS sent successfully', 'fr': 'SMS envoyé avec succès'},
    'sms_failed': {'en': 'Failed to send SMS', 'fr': 'Échec de l\'envoi du SMS'},
    'sms_queued': {'en': 'SMS queued for delivery', 'fr': 'SMS en file d\'attente'},

    # Payment
    'payment_initiated': {'en': 'Payment initiated. Confirm on your phone.', 'fr': 'Paiement initié. Confirmez sur votre téléphone.'},
    'payment_completed': {'en': 'Payment completed successfully', 'fr': 'Paiement effectué avec succès'},
    'payment_failed': {'en': 'Payment failed. Please try again.', 'fr': 'Paiement échoué. Veuillez réessayer.'},
    'payment_pending': {'en': 'Payment is pending confirmation', 'fr': 'Paiement en attente de confirmation'},
    'select_student_course': {'en': 'Please select both a student and a course', 'fr': 'Veuillez sélectionner un étudiant et un cours'},

    # MINESEC
    'minesec_report_generated': {'en': 'MINESEC XML report generated', 'fr': 'Rapport XML MINESEC généré'},
    'minesec_report_failed': {'en': 'Failed to generate MINESEC report', 'fr': 'Échec de la génération du rapport MINESEC'},

    # Dashboard labels missing from translations
    'live_checkins': {'en': 'Live Check-ins', 'fr': 'Arrivées en direct'},
    'live_alerts': {'en': 'Live Alerts', 'fr': 'Alertes en direct'},
    'todays_checkins': {'en': 'Today\'s Check-ins', 'fr': 'Arrivées du jour'},
    'attendance_rate_live': {'en': 'Attendance Rate', 'fr': 'Taux de présence'},
    'fraud_alerts': {'en': 'Fraud Alerts', 'fr': 'Alertes de fraude'},
    'running_now': {'en': 'Running now', 'fr': 'En cours'},
    'realtime_count': {'en': 'Real-time count', 'fr': 'Compteur en direct'},
    'live_average': {'en': 'Live average', 'fr': 'Moyenne en direct'},
    'requires_attention': {'en': 'Requires attention', 'fr': 'Nécessite attention'},
    'montant_xaf': {'en': 'Amount (XAF)', 'fr': 'Montant (XAF)'},

    # User management labels
    'add_user': {'en': 'Add User', 'fr': 'Ajouter un utilisateur'},
    'edit_user': {'en': 'Edit User', 'fr': 'Modifier l\'utilisateur'},
    'add_course': {'en': 'Add Course', 'fr': 'Ajouter un cours'},
    'edit_course': {'en': 'Edit Course', 'fr': 'Modifier le cours'},
    'add_department': {'en': 'Add Department', 'fr': 'Ajouter un département'},
    'edit_department': {'en': 'Edit Department', 'fr': 'Modifier le département'},
    'enroll_student': {'en': 'Enroll Student', 'fr': 'Inscrire un étudiant'},
    'user_management': {'en': 'User Management', 'fr': 'Gestion des utilisateurs'},
    'course_management': {'en': 'Course Management', 'fr': 'Gestion des cours'},
    'department_management': {'en': 'Department Management', 'fr': 'Gestion des départements'},
    'enrollment_management': {'en': 'Enrollment Management', 'fr': 'Gestion des inscriptions'},
    'search': {'en': 'Search...', 'fr': 'Rechercher...'},
    'search_name_email': {'en': 'Search name, email...', 'fr': 'Rechercher nom, email...'},
    'search_name_code': {'en': 'Search name, code...', 'fr': 'Rechercher nom, code...'},
    'search_student': {'en': 'Search student...', 'fr': 'Rechercher étudiant...'},
    'name': {'en': 'Name', 'fr': 'Nom'},
    'email': {'en': 'Email', 'fr': 'Email'},
    'role': {'en': 'Role', 'fr': 'Rôle'},
    'phone': {'en': 'Phone', 'fr': 'Téléphone'},
    'status': {'en': 'Status', 'fr': 'Statut'},
    'actions': {'en': 'Actions', 'fr': 'Actions'},
    'active': {'en': 'Active', 'fr': 'Actif'},
    'disabled': {'en': 'Disabled', 'fr': 'Désactivé'},
    'inactive': {'en': 'Inactive', 'fr': 'Inactif'},
    'code': {'en': 'Code', 'fr': 'Code'},
    'credits': {'en': 'Credits', 'fr': 'Crédits'},
    'dept': {'en': 'Dept', 'fr': 'Dép.'},
    'head': {'en': 'Head', 'fr': 'Chef'},
    'student': {'en': 'Student', 'fr': 'Étudiant'},
    'course': {'en': 'Course', 'fr': 'Cours'},
    'date': {'en': 'Date', 'fr': 'Date'},
    'cancel': {'en': 'Cancel', 'fr': 'Annuler'},
    'save': {'en': 'Save', 'fr': 'Enregistrer'},
    'delete_confirm': {'en': 'Are you sure?', 'fr': 'Êtes-vous sûr ?'},

    # Payment labels
    'process_payment': {'en': 'Process Payment', 'fr': 'Effectuer le paiement'},
    'initiate_payment': {'en': 'Initiate Payment', 'fr': 'Initier le paiement'},
    'select_provider': {'en': 'Select Provider', 'fr': 'Choisir le fournisseur'},
    'phone_number': {'en': 'Phone Number', 'fr': 'Numéro de téléphone'},
    'amount_xaf': {'en': 'Amount (XAF)', 'fr': 'Montant (XAF)'},
    'payment_confirm_phone': {'en': 'Confirm on your phone via {provider}', 'fr': 'Confirmez sur votre téléphone via {provider}'},
}


def t(key: str, lang: str = 'en', **kwargs) -> str:
    """Get translated string by key and language."""
    entry = TRANSLATIONS.get(key)
    if not entry:
        return key
    val = entry.get(lang, entry.get('en', key))
    if kwargs:
        try:
            val = val.format(**kwargs)
        except KeyError:
            pass
    return val


def translate_error(key: str, lang: str = 'en', **kwargs) -> dict:
    """Return a bilingual error response dict."""
    return {
        'error': t(key, 'en', **kwargs),
        'error_fr': t(key, 'fr', **kwargs),
    }
