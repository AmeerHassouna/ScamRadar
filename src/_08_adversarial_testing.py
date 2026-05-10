"""
ScamRadar+ | Step 08: Adversarial Robustness Testing
Tests model against l33t speak, emoji substitution, extra spaces, mixed case
"""

from src._02_feature_engineering import normalize_leet


def test_adversarial(original_message, variants, predict_fn):
    print(f"Original: {original_message}")
    result = predict_fn(original_message)
    print(f"→ {result['verdict']} ({result['confidence']}% confidence)\n")

    for name, variant in variants.items():
        print(f"Variant [{name}]: {variant}")
        result = predict_fn(variant)
        print(f"→ {result['verdict']} ({result['confidence']}% confidence)\n")
    print("="*60)


def run_all_adversarial_tests(predict_fn):
    print("\n" + "="*60)
    print("ADVERSARIAL ROBUSTNESS TESTING")
    print("="*60 + "\n")

    # Test Case 1: Prize/Gift Card Scam
    test_adversarial(
        "Congratulations! You won a free $1000 gift card. Click here to claim now!",
        {
            "L33t speak":   "C0ngr4tul4t10ns! Y0u w0n a fr33 $1000 g1ft c4rd. Cl1ck h3r3 t0 cl41m n0w!",
            "Extra spaces": "C o n g r a t u l a t i o n s ! You  won  a  free  gift  card. Click here!",
            "Emoji sub":    "C🎉ngratulations! You w🏆n a fr🎁e gift card. Cl🖱ck here to claim n🕐w!",
            "Mixed case":   "cOnGrAtUlAtIoNs! yOu WoN a FrEe GiFt CaRd. cLiCk HeRe!",
            "Punctuation":  "C-o-n-g-r-a-t-u-l-a-t-i-o-n-s! You won a free gift card. Click here!"
        },
        predict_fn
    )

    # Test Case 2: Bank/Account Scam
    test_adversarial(
        "URGENT: Your bank account has been suspended. Verify immediately at http://paypal-secure.tk",
        {
            "L33t speak":   "URG3NT: Y0ur b4nk 4cc0unt h4s b33n susp3nd3d. V3r1fy 1mm3d14t3ly",
            "Extra spaces": "U R G E N T : Your  bank  account  has  been  suspended. Verify now",
            "Emoji sub":    "🚨URGENT🚨: Your bank account has been suspended. Verify immediately!",
            "Mixed case":   "uRgEnT: yOuR bAnK aCcOuNt HaS bEeN sUsReNdEd. vErIfY iMmEdIaTeLy",
        },
        predict_fn
    )

    print("\n✅ Adversarial testing complete!")
    print("Note: L33t speak normalization is applied in predict_message_v2()")
