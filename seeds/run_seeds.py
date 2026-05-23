def run_all_seeds():
    from seeds.question_type_seeds import seed_question_types
    from seeds.super_admin_seed import seed_super_admin

    seed_super_admin()
    seed_question_types()
