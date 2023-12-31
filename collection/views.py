from django.shortcuts import render
from pokemontcgsdk import Set as TcgSet, Card as TcgCard
from datetime import datetime, timedelta
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.conf import settings
from pokemontcgsdk import RestClient
from .models import Set, Card, MyCollection 

RestClient.configure(settings.POKEMONTCG_IO_API_KEY)

from datetime import datetime
from .models import Set  
from pokemontcgsdk import Set as TcgSet  

def populate_sets_to_database():
    """
    Populate the Set model in the database using data fetched from an API.

    Parameters:
    None

    Returns:
    None
    """
    sets = TcgSet.all()  # Fetch sets from the API
    print(f"Number of sets fetched: {len(sets)}")

    for set in sets:
        logo_url = set.images.logo if hasattr(set.images, 'logo') else None  # Check if logo exists in the API response

        # Use update_or_create to either update the existing set or create a new one
        db_set, created = Set.objects.update_or_create(
            name=set.name, 
            defaults={
                'releaseDate': datetime.strptime(set.releaseDate, "%Y/%m/%d").date(),  
                'logo': logo_url
            }
        )

        if created:
            print(f"Created new set: {set.name}")
        else:
            print(f"Updated existing set: {set.name}")

def populate_cards_to_database():
    """
    Populate the Card model in the database using data fetched from an API.

    Parameters:
    None

    Returns:
    None
    """
    page = 1
    page_size = 250
    
    while True:
        try:
            # Fetch the cards from the API for the current page
            cards = TcgCard.where(page=page, pageSize=page_size)
            print(f"Fetched {len(cards)} cards from page {page}.")

            # Break if no cards are fetched (indicates the last page was reached)
            if not cards:
                break

            for card in cards:
                # Check if the card already exists in our database by card_id to avoid duplicates
                if card.set and not Card.objects.filter(card_id=card.id).exists():
                    # Try to get the set from the database
                    set_obj = Set.objects.filter(name=card.set.name).first() if card.set else None

                    # Create a new Card instance and populate the fields
                    db_card = Card(
                        card_id=card.id,
                        name=card.name,
                        image=card.images.large if card.images and hasattr(card.images, 'large') else None,
                        set=set_obj
                    )
                    
                    # Save the Card instance to the database
                    db_card.save()
                    print(f"Saved card: {card.name}")

        except Exception as e:
            print(f"Error occurred while fetching cards from page {page}: {e}")

        # Move to the next page for the next iteration
        page += 1

def populate_data(request):
    """
    Wrapper function to populate both sets and cards into the database.

    Parameters:
    - request: The HTTP request object

    Returns:
    HttpResponse indicating the success or failure of the operation.
    """
    populate_sets_to_database()
    populate_cards_to_database()
    print("Data populated successfully!")
    return HttpResponse("Data populated successfully!")


def collection_view(request):
    """
    Renders a view that displays recent sets from the Set model in the database.

    Parameters:
    - request: The HTTP request object

    Returns:
    Rendered HTML page with data on recent sets.
    """
    two_years_ago = (datetime.now() - timedelta(days=364)).date()  
    all_sets = Set.objects.all()
    recent_sets = [set for set in all_sets if set.releaseDate and set.releaseDate >= two_years_ago]
    return render(request, 'collection.html', {'sets': recent_sets})



def cards_view(request, set_id=None):
    """
    Renders a view that displays cards based on the selected set.

    Parameters:
    - request: The HTTP request object
    - set_id: The ID of the set to filter cards by (optional)

    Returns:
    Rendered HTML page with data on cards.
    """
    set_name = None
    user_collection = None  
    
    if set_id:
        set_obj = Set.objects.filter(id=set_id).first()
        if set_obj:
            cards = Card.objects.filter(set=set_obj)
            set_name = set_obj.name
    else:
        # This is an example, fetching cards from the "generations" set, you can change this logic
        set_obj = Set.objects.filter(name='generations').first()
        cards = Card.objects.filter(set=set_obj) if set_obj else []
    
    if request.user.is_authenticated:  # Check if user is authenticated
        # Get the user's collection
        user_collection, created = MyCollection.objects.get_or_create(user=request.user)

        
        for card in cards:
            card.in_collection = card in user_collection.cards.all()
    
    return render(request, 'cards.html', {'cards': cards, 'collection_name': set_name})



@login_required
def my_collection(request):
    """
    Renders a view showing all the cards in the authenticated user's collection.

    Parameters:
    - request: The HTTP request object

    Returns:
    Rendered HTML page with data on the user's collection.
    """
    my_collection, created = MyCollection.objects.get_or_create(user=request.user)
    cards = my_collection.cards.all()
    return render(request, 'my_collection.html', {'cards': cards})


@login_required
def add_card_to_collection(request, id):
    """
    Adds a selected card to the authenticated user's collection.

    Parameters:
    - request: The HTTP request object
    - id: The ID of the card to add to the collection

    Returns:
    JsonResponse indicating the success or failure of the operation.
    """
    user = request.user
    print(f"Trying to add card with ID {id} to collection for user {user.username}")
    
    try:
        my_collection, _ = MyCollection.objects.get_or_create(user=user)
        print("Available Cards:", Card.objects.values('id'))

        card = Card.objects.get(id=id)
        if card in my_collection.cards.all():
            return JsonResponse({
                'success': False,
                'message': 'Card already added to your collection!'
            })
        
        my_collection.cards.add(card)
        print(f"Successfully added card with ID {id} to collection for user {user.username}")
        
        return JsonResponse({
            'success': True,
            'message': f'Card with successfully added to your collection!'
        })
    except Card.DoesNotExist:
        print(f"Card with ID {id} does not exist.")
        return JsonResponse({
            'success': False,
            'message': f'Card not found!'
        })
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'An unexpected error occurred: {str(e)}'
        })



@login_required
def remove_card_from_collection(request, id):
    """
    Removes a selected card from the authenticated user's collection.

    Parameters:
    - request: The HTTP request object
    - id: The ID of the card to remove from the collection

    Returns:
    JsonResponse indicating the success or failure of the operation.
    """
    user = request.user
    try:
        # Retrieve the UserCollection for the user
        my_collection = MyCollection.objects.get(user=user)

        # Get the Card instance
        card = Card.objects.get(id=id)

        # Remove the card from the collection
        my_collection.cards.remove(card)

        return JsonResponse({
            'success': True,
            'message': 'Card successfully removed from your collection!'
        })
    except MyCollection.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Collection not found!'
        })
    except Card.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Card not found!'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })
